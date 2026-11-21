# coding: utf-8
# SPDX-License-Identifier: GPL-3.0-or-later
"""Deliver native battle state to the Solid Color Reticle HUD."""
from __future__ import absolute_import

import logging
import math

import BigWorld
from gui.Scaleform.daapi.view.battle.shared.crosshair.container import CrosshairPanelContainer
from gui.Scaleform.daapi.view.meta.CrosshairPanelContainerMeta import CrosshairPanelContainerMeta
import white_blade_minimum
from white_blade_penetration import estimate


_NAN = float('nan')
_EMPTY_AIM = (_NAN, _NAN, _NAN)
_AIM_INTERVAL = 1.0 / 30
_SHELL_NAMES = {'ARMOR_PIERCING': 'AP', 'ARMOR_PIERCING_CR': 'APCR',
                'ARMOR_PIERCING_HE': 'APHE', 'HOLLOW_CHARGE': 'HEAT',
                'HIGH_EXPLOSIVE': 'HE', 'SMOKE': 'SMOKE'}
_DATA_FIELDS = ('health', 'maxHealth', 'total', 'burstTime', 'height', 'flight',
                'penetration', 'splash', 'splashRadiusX', 'splashRadiusY',
                'splashRotation', 'splashX', 'splashY', 'aimArmor', 'aimChance', 'aimColor')
_TRAVERSE_FIELDS = ('traverseLeft', 'traverseRight', 'traverseLeftRatio', 'traverseRightRatio', 'traverseRotation')
_READY_KEY = '#ingame_gui:chat_shortcuts/reloading_ready'
_logger = logging.getLogger('solid_color_reticle')
_errors = 0
_installed = False
_active = None


def _log(where):
    global _errors
    if _errors < 5:
        _errors += 1
        _logger.exception('White Blade: %s (log %d/5)', where, _errors)


def _number(value):
    try:
        value = float(value)
        return value if value >= 0 and not math.isinf(value) else _NAN
    except (TypeError, ValueError, OverflowError):
        return _NAN


def _ready_text():
    try:
        from helpers import getClientLanguage
        from helpers.i18n import makeString
        if getClientLanguage() in ('zh_cn', 'zh_tw', 'cn'):
            return 'Ready'
        text = makeString(_READY_KEY)
        if isinstance(text, basestring) and text and text not in (_READY_KEY, _READY_KEY[1:], _READY_KEY.split(':', 1)[1]):
            return text
    except Exception:
        _log('ready text')
    return 'Ready'


class _Bridge(object):
    def __init__(self, panel):
        self.panel = panel
        self.callback = None
        self.flights = {}
        self.reload_gun = None
        self.full_reload = _NAN
        self.vehicle_id = None
        self.is_spg = False
        self.geometry = None
        self.missing_ticks = 0
        self.warned_missing = False
        self.ready_text = _ready_text()
        self.marker_names = {}
        self.marker_targets = {}
        self.aim = {}
        self.aim_receivers = ()
        self.aim_pending = None
        self.aim_callback = None
        self.aim_next = 0.
        self.auto_aim_id = None
        self.target_events = []
        self.target_bus = None
        self.resolver = None
        self.shot_colors = {}
        self.team = 0
        self.piercing = 1
        self.feedback_event = None
        self.settings_core = None
        self.alt_colors = {}
        self.color_blind_key = None
        try:
            from white_blade_geometry import Geometry
            self.geometry = Geometry()
        except Exception:
            _log('geometry init')

    def start_targets(self):
        # Use the client's collision/resolver; no guessed armor or penetration math.
        try:
            from AvatarInputHandler.gun_marker_ctrl import createShotResultResolver
            from gui.Scaleform.daapi.view.battle.shared.crosshair.settings import SHOT_RESULT_TO_DEFAULT_COLOR, SHOT_RESULT_TO_ALT_COLOR
            from gui.battle_control.battle_constants import FEEDBACK_EVENT_ID
            from account_helpers.settings_core.settings_constants import GRAPHICS
            from helpers import dependency
            from skeletons.account_helpers.settings_core import ISettingsCore
            from gui.shared import g_eventBus, EVENT_BUS_SCOPE
            from gui.shared.events import GameEvent
            self.resolver = createShotResultResolver()
            self.shot_colors = SHOT_RESULT_TO_DEFAULT_COLOR
            self.alt_colors = SHOT_RESULT_TO_ALT_COLOR
            self.settings_core = dependency.instance(ISettingsCore)
            self.color_blind_key = GRAPHICS.COLOR_BLIND
            self.feedback_event = FEEDBACK_EVENT_ID.VEHICLE_ATTRS_CHANGED
            self.team = self.panel.sessionProvider.getArenaDP().getNumberOfTeam()
            ctrl = self.panel.sessionProvider.shared.crosshair
            for event, handler in ((ctrl.onGunMarkerStateChanged, self.marker_state),
                                   (ctrl.onCrosshairViewChanged, self.clear_colors),
                                   (self.panel.sessionProvider.shared.feedback.onVehicleFeedbackReceived, self.feedback)):
                event += handler
                self.target_events.append((event, handler))
            # Lock changes invalidate the previous collision before the next aim update.
            g_eventBus.addListener(GameEvent.ON_TARGET_VEHICLE_CHANGED, self.clear_colors, scope=EVENT_BUS_SCOPE.BATTLE)
            self.target_bus = (g_eventBus, GameEvent.ON_TARGET_VEHICLE_CHANGED, EVENT_BUS_SCOPE.BATTLE)
            ammo = self.panel.sessionProvider.shared.ammo
            for source, name in ((ctrl, 'onGunMarkersSetChanged'), (ammo, 'onCurrentShellChanged')):
                event = getattr(source, name, None)
                if event is not None:
                    handler = self.clear_colors
                    event += handler
                    self.target_events.append((event, handler))
        except Exception:
            _log('target subscription')

    def primary_aim_marker(self):
        from aih_constants import GUN_MARKER_TYPE
        from gui.battle_control.battle_constants import CROSSHAIR_VIEW_ID
        if self.is_spg or self.panel.getViewID() not in (CROSSHAIR_VIEW_ID.ARCADE, CROSSHAIR_VIEW_ID.SNIPER):
            return None
        info = self.panel.sessionProvider.shared.crosshair.getGunMarkersSetInfo()
        if info.isServerMarkerActivated:
            return GUN_MARKER_TYPE.SERVER
        if info.isClientMarkerActivated:
            return GUN_MARKER_TYPE.CLIENT
        return None

    def aim_estimate(self, marker, entity):
        import constants
        from AvatarInputHandler.gun_marker_ctrl import _CrosshairShotResults
        from Vehicle import Vehicle
        player = BigWorld.player()
        if (not isinstance(entity, Vehicle) or entity.health <= 0 or not entity.isCrewActive
                or entity.publicInfo['team'] == self.team or BigWorld.entity(entity.id) is not entity
                or player is None):
            return None
        vehicle = self.vehicle()
        if vehicle is None or player.getVehicleAttached() is not vehicle:
            return None
        if self.is_spg:
            return None
        modifiers = self.panel.sessionProvider.arenaVisitor.modifiers.getConstantsModification()
        anchors = (modifiers.PIERCING_POWER_INTERPOLATION_DIST_FIRST,
                   modifiers.PIERCING_POWER_INTERPOLATION_DIST_LAST)
        return estimate(marker, player, _CrosshairShotResults._getAllCollisionDetails,
                        self.piercing, anchors, constants.SHELL_MECHANICS_TYPE.MODERN)

    def push_aim(self, aim):
        receivers = []
        for receive in self.aim_receivers:
            try:
                if receive(*(aim if aim is not None else _EMPTY_AIM)) is True:
                    receivers.append(receive)
            except Exception:
                _log('GFx aim')
        self.aim_receivers = tuple(receivers)

    def cancel_aim(self):
        self.aim_pending = None
        callback, self.aim_callback = self.aim_callback, None
        if callback is not None:
            try:
                BigWorld.cancelCallback(callback)
            except Exception:
                _log('cancel aim callback')

    def flush_aim(self, callback):
        if self.aim_callback != callback:
            return
        self.aim_callback = None
        pending, self.aim_pending = self.aim_pending, None
        if pending is not None and self.panel is not None:
            marker_type, marker, entity = pending
            try:
                if marker_type == self.primary_aim_marker() and self.marker_targets.get(marker_type) is entity:
                    self.aim_next = BigWorld.time() + _AIM_INTERVAL
                    self.resolve_marker(marker_type, marker, entity, True)
            except Exception:
                _log('pending aim update')

    def resolve_marker(self, marker_type, marker, entity, primary):
        color, aim = 'normal', None
        if entity is not None:
            self.team = self.panel.sessionProvider.getArenaDP().getNumberOfTeam()
        if primary and entity is not None:
            try:
                aim = self.aim_estimate(marker, entity)
                if aim is not None:
                    aim = (round(aim[0]), aim[1], aim[2])
            except Exception:
                _log('aim penetration estimate')
        try:
            if aim is not None:
                color = 'wb%06x' % aim[2]
            elif entity is not None:
                result = self.resolver.getShotResult(marker, excludeTeam=self.team, piercingMultiplier=self.piercing)
                colors = self.alt_colors if self.settings_core.getSetting(self.color_blind_key) else self.shot_colors
                color = colors.get(result, 'normal')
        except Exception:
            _log('native shot result')
        try:
            self.panel.setGunMarkerColor(marker_type, color)
        except Exception:
            aim = None
            _log('marker color')
        self.marker_targets[marker_type] = entity
        previous = self.aim.pop(marker_type, None)
        if aim is not None:
            self.aim[marker_type] = aim
        if previous != aim:
            self.push_aim(aim)

    def marker_state(self, marker_type, gun_marker_state, support_markers_info):
        if self.panel is None:
            return
        try:
            collision = gun_marker_state.collData
            entity = collision.entity if collision is not None else None
            previous = self.marker_targets.get(marker_type)
            if entity is None and previous is None:
                return
            self.marker_targets[marker_type] = entity
            primary = hasattr(self.panel, 'getViewID') and marker_type == self.primary_aim_marker()
            if primary:
                now = BigWorld.time()
                # Capture only the newest event between samples. Acquiring or losing a target bypasses the interval.
                if entity is not None and entity is previous and now < self.aim_next:
                    self.aim_pending = (marker_type, gun_marker_state, entity)
                    if self.aim_callback is None:
                        callback = BigWorld.callback(self.aim_next - now, lambda: self.flush_aim(callback))
                        self.aim_callback = callback
                    return
                self.cancel_aim()
                self.aim_next = now + _AIM_INTERVAL if entity is not None else 0.
            self.resolve_marker(marker_type, gun_marker_state, entity, primary)
        except Exception:
            _log('marker update')

    def feedback(self, event_id, vehicle_id, value):
        if event_id == self.feedback_event:
            piercing = value.get('gunPiercing', 1)
            if piercing != self.piercing:
                self.piercing = piercing
                self.clear_colors()

    def clear_colors(self, *unused):
        self.cancel_aim()
        self.aim_next = 0.
        if self.aim:
            self.aim.clear()
            self.push_aim(None)
        self.marker_targets.clear()
        for name in tuple(self.marker_names):
            self.panel.as_setGunMarkerColorS(name, 'normal')

    def check_targets(self):
        try:
            player = BigWorld.player()
            locked = player.autoAimVehicle if player is not None else None
            ident = locked.id if locked is not None else None
            if ident != self.auto_aim_id:
                self.clear_colors()
                self.auto_aim_id = ident
        except Exception:
            _log('auto aim state')
        for marker_type, entity in self.marker_targets.items():
            if entity is None:
                continue
            try:
                valid = entity.health > 0 and getattr(entity, 'isCrewActive', True) and BigWorld.entity(entity.id) is entity
            except Exception:
                valid = False
            if not valid:
                if self.aim_pending is not None and self.aim_pending[0] == marker_type:
                    self.cancel_aim()
                if self.aim.pop(marker_type, None) is not None:
                    self.push_aim(None)
                self.panel.setGunMarkerColor(marker_type, 'normal')
                self.marker_targets[marker_type] = None

    def vehicle(self):
        vehicle = self.panel.sessionProvider.shared.vehicleState.getControllingVehicle()
        vehicle_id = vehicle.id if vehicle is not None else None
        if vehicle_id != self.vehicle_id:
            if self.vehicle_id is not None:
                self.clear_colors()
            self.flights.clear()
            self.reload_gun = None
            self.full_reload = _NAN
            self.vehicle_id = vehicle_id
            vehicle_type = getattr(vehicle.typeDescriptor, 'type', None) if vehicle is not None else None
            self.is_spg = getattr(vehicle_type, 'classTag', None) == 'SPG'
        return vehicle

    def observe_flights(self, values):
        vehicle = self.vehicle()
        if not values or vehicle is None:
            self.flights.clear()
            return
        valid = tuple(shot.shell.compactDescr for shot in vehicle.typeDescriptor.gun.shots)
        # Native __onShellsUpdated sends a one-element delta, not a snapshot.
        for row in values:
            if isinstance(row, dict) and row.get('shellIntCD') in valid:
                self.flights[row['shellIntCD']] = _number(row.get('flyTime'))

    def impact_flight(self, vehicle, shot):
        player = BigWorld.player()
        handler = getattr(player, 'inputHandler', None)
        if handler is None:
            return _NAN
        from aih_constants import CTRL_MODE_NAME
        if handler.ctrlModeName not in (CTRL_MODE_NAME.STRATEGIC, CTRL_MODE_NAME.ARTY):
            return _NAN
        if player.getVehicleAttached() is not vehicle:
            return _NAN
        aim_point = handler.getDesiredShotPoint(ignoreAimingMode=True)
        if aim_point is None:
            return _NAN

        # The original SPG HUD clears NOT_HIT, including when terrain intercepts the shot.
        # Use the same native trajectory and timing APIs with the first impact as the endpoint.
        from AvatarInputHandler.AimingSystems import CollisionStrategy, getCappedShotTargetInfos
        from AvatarInputHandler.spg_marker_helpers.spg_marker_helpers import getSPGShotFlyTime
        origin, velocity, gravity = player.gunRotator.getShotParams(
            aim_point, ignoreYawLimits=True, overrideShotDescr=shot)
        lower, upper = player.arena.getSpaceBB()
        impact, _, _, used_max_distance = getCappedShotTargetInfos(
            origin, velocity, gravity, shot, player.playerVehicleID, lower, upper,
            CollisionStrategy.COLLIDE_DYNAMIC_AND_STATIC)
        if impact is None or used_max_distance:
            return _NAN
        attrs = self.panel.sessionProvider.shared.feedback.getVehicleAttrs()
        duration = _number(getSPGShotFlyTime(impact, velocity, origin, shot.maxDistance, shot.speed, attrs))
        return duration if duration > 0 else _NAN

    def full_reload_time(self, gun, clip_size, base, interval):
        if gun is not self.reload_gun:
            self.reload_gun = gun
            self.full_reload = _NAN
        if clip_size <= 1 or interval == 0:
            return base
        # The native snapshot can replace baseTime with the clip interval between shots.
        if base > 0 and interval > 0 and abs(base - interval) > 1e-4:
            self.full_reload = base
        if self.full_reload > 0:
            return self.full_reload
        # ponytail: before the first full snapshot, show the gun's nominal duration.
        return _number(getattr(gun, 'reloadTime', None))

    def sample(self):
        data = dict.fromkeys(_DATA_FIELDS + _TRAVERSE_FIELDS, _NAN)
        data.update(shell='', readyText=self.ready_text)
        self.check_targets()
        vehicle = None
        try:
            vehicle = self.vehicle()
            if vehicle is not None:
                data['health'] = _number(vehicle.health)
                data['maxHealth'] = _number(vehicle.maxHealth)
        except Exception:
            self.flights.clear()
            _log('vehicle state')
        ammo = None
        base_reload = _NAN
        try:
            ammo = self.panel.sessionProvider.shared.ammo
            if ammo is not None:
                base_reload = _number(ammo.getGunReloadingState().getBaseValue())
        except Exception:
            _log('reload base time')
        if ammo is not None:
            try:
                # _AmmoSettings delegates to this getter: automatic fire is 0.
                settings = ammo.getGunSettings()
                data['burstTime'] = _number(settings.getClipInterval())
                if vehicle is not None:
                    data['total'] = self.full_reload_time(
                        vehicle.typeDescriptor.gun, settings.clip.size, base_reload, data['burstTime'])
            except Exception:
                _log('gun reload settings')
            try:
                current = ammo.getCurrentShellCD()
                data['flight'] = self.flights.get(current, _NAN)
                if vehicle is not None:
                    for shot in vehicle.typeDescriptor.gun.shots:
                        shell = shot.shell
                        if shell.compactDescr != current:
                            continue
                        data['shell'] = _SHELL_NAMES.get(shell.kind, shell.kind)
                        power = getattr(shot, 'piercingPower', ())
                        if power:
                            # Native ammo_ctrl._GunSettings.fromVehicle, source line 119.
                            data['penetration'] = _number(power[0])
                        # Native vehicles._readShellLocal, source lines 8869/8956/9027.
                        data['splash'] = _number(getattr(shell.type, 'explosionRadius', None))
                        if not data['flight'] > 0:
                            data['flight'] = self.impact_flight(vehicle, shot)
                        break
            except Exception:
                _log('current shell')
        if self.aim:
            aim = self.aim.get(self.primary_aim_marker())
            if aim is not None:
                data.update(aimArmor=aim[0], aimChance=aim[1], aimColor=aim[2])
        if self.geometry is not None:
            try:
                footprint, traverse = self.geometry.sample(self.panel, data['splash'], vehicle, _log)
                data.update(footprint)
                data.update(zip(_TRAVERSE_FIELDS, traverse))
            except Exception:
                _log('geometry sample')
        return data

    def schedule(self):
        if _active is self and self.panel is not None and self.callback is None:
            try:
                self.callback = BigWorld.callback(0.1, self.tick)
            except Exception:
                _log('schedule')
                _stop(self.panel)

    def tick(self):
        self.callback = None
        if _active is not self or self.panel is None:
            return
        try:
            if not self.panel._isDAAPIInited():
                _stop(self.panel)
                return
            data = self.sample()
            found = False
            aim_receivers = []
            flash = self.panel.flashObject
            # Native initCrosshairs adds the wrappers directly; Timeline.name is read-only.
            for index in range(int(flash.numChildren)):
                try:
                    child = flash.getChildAt(index)
                    receive = getattr(child, 'as_whiteBladeData', None)
                    # An undefined GFx dynamic method may still be callable: require ACK.
                    if callable(receive) and receive(data) is True:
                        found = True
                        receive_aim = getattr(child, 'as_whiteBladeAim', None)
                        if callable(receive_aim):
                            aim_receivers.append(receive_aim)
                except Exception:
                    _log('GFx child %d' % index)
            self.aim_receivers = tuple(aim_receivers)
            self.missing_ticks = 0 if found else self.missing_ticks + 1
            if self.missing_ticks >= 10 and not self.warned_missing:
                self.warned_missing = True
                _logger.warning('White Blade: no HUD wrapper ACK after 1s; '
                                'check SWF installation and GFx access.')
        except Exception:
            _log('tick')
        finally:
            self.schedule()

    def stop(self):
        for event, handler in self.target_events:
            try:
                event -= handler
            except Exception:
                _log('target unsubscribe')
        self.target_events[:] = []
        if self.target_bus is not None:
            bus, kind, scope = self.target_bus
            try:
                bus.removeListener(kind, self.clear_colors, scope=scope)
            except Exception:
                _log('target event unsubscribe')
            self.target_bus = None
        self.cancel_aim()
        self.aim.clear()
        self.aim_receivers = ()
        self.marker_targets.clear()
        self.marker_names.clear()
        callback, self.callback = self.callback, None
        self.panel = None
        self.geometry = None
        self.flights.clear()
        if callback is not None:
            try:
                BigWorld.cancelCallback(callback)
            except Exception:
                _log('cancel callback')


def _stop(panel=None):
    global _active
    if _active is not None and (panel is None or _active.panel is panel):
        state, _active = _active, None
        white_blade_minimum.stop()
        state.stop()


def init():
    global _installed
    if _installed:
        return
    original_populate = CrosshairPanelContainer._populate
    original_dispose = CrosshairPanelContainer._dispose
    original_flights = CrosshairPanelContainerMeta.as_setShotFlyTimesS
    original_color = CrosshairPanelContainerMeta.as_setGunMarkerColorS

    def populate(panel, *args, **kwargs):
        global _active
        # Reserve state before native plugin startup so its first flight event is
        # captured. Polling only starts AFTER the native populate has succeeded.
        try:
            _stop()
            _active = _Bridge(panel)
            white_blade_minimum.start()
        except Exception:
            _log('populate bridge')
        try:
            result = original_populate(panel, *args, **kwargs)
        except Exception:
            _stop(panel)
            raise
        if _active is not None and _active.panel is panel:
            _active.start_targets()
            _active.schedule()
        return result

    def dispose(panel, *args, **kwargs):
        try:
            return original_dispose(panel, *args, **kwargs)
        finally:
            _stop(panel)

    def flights(panel, values, *args, **kwargs):
        result = original_flights(panel, values, *args, **kwargs)
        if _active is not None and _active.panel is panel:
            try:
                _active.observe_flights(values)
            except Exception:
                _log('flight update')
        return result

    def marker_color(panel, name, color, *args, **kwargs):
        state = _active if _active is not None and _active.panel is panel else None
        previous = state.marker_names.get(name) if state is not None else None
        if previous is not None and previous[0] == color:
            return previous[1]
        result = original_color(panel, name, color, *args, **kwargs)
        if state is not None:
            if color == 'normal':
                state.marker_names.pop(name, None)
            else:
                state.marker_names[name] = (color, result)
        return result

    CrosshairPanelContainer._populate = populate
    CrosshairPanelContainer._dispose = dispose
    CrosshairPanelContainerMeta.as_setShotFlyTimesS = flights
    CrosshairPanelContainerMeta.as_setGunMarkerColorS = marker_color
    try:
        white_blade_minimum.install(_log)
    except Exception:
        _log('install minimum markers')
    _installed = True


def fini():
    _stop()


init()
