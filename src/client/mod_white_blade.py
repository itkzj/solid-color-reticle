# coding: utf-8
# SPDX-License-Identifier: GPL-3.0-or-later
"""Deliver native battle state to the Solid Color Reticle HUD."""
from __future__ import absolute_import

import logging
import math

import BigWorld
from gui.Scaleform.daapi.view.battle.shared.crosshair.container import CrosshairPanelContainer
from gui.Scaleform.daapi.view.meta.CrosshairPanelContainerMeta import CrosshairPanelContainerMeta


_NAN = float('nan')
_SHELL_NAMES = {'ARMOR_PIERCING': 'AP', 'ARMOR_PIERCING_CR': 'APCR',
                'ARMOR_PIERCING_HE': 'APHE', 'HOLLOW_CHARGE': 'HEAT',
                'HIGH_EXPLOSIVE': 'HE', 'SMOKE': 'SMOKE'}
_DATA_FIELDS = ('health', 'maxHealth', 'total', 'fullReloadTime', 'burstTime', 'height', 'flight',
                'penetration', 'splash', 'splashPixels', 'splashRadiusX', 'splashRadiusY',
                'splashRotation', 'splashX', 'splashY')
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
        self.geometry = None
        self.missing_ticks = 0
        self.warned_missing = False
        self.ready_text = _ready_text()
        self.marker_names = set()
        self.marker_targets = {}
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
            g_eventBus.addListener(GameEvent.ON_TARGET_VEHICLE_CHANGED, self.target_changed, scope=EVENT_BUS_SCOPE.BATTLE)
            self.target_bus = (g_eventBus, GameEvent.ON_TARGET_VEHICLE_CHANGED, EVENT_BUS_SCOPE.BATTLE)
        except Exception:
            _log('target subscription')

    def marker_state(self, marker_type, gun_marker_state, support_markers_info):
        if self.panel is None:
            return
        color = 'normal'
        self.marker_targets[marker_type] = None
        try:
            self.team = self.panel.sessionProvider.getArenaDP().getNumberOfTeam()
            # CN 2.4.1.1 sends a GunMarkerState object plus support-marker info.
            # Match the installed ShotResultIndicatorPlugin and its resolver API.
            result = self.resolver.getShotResult(gun_marker_state, excludeTeam=self.team, piercingMultiplier=self.piercing)
            colors = self.alt_colors if self.settings_core.getSetting(self.color_blind_key) else self.shot_colors
            color = colors.get(result, 'normal')
            collision = gun_marker_state.collData
            self.marker_targets[marker_type] = collision.entity if collision is not None else None
        except Exception:
            _log('native shot result')
        try:
            self.panel.setGunMarkerColor(marker_type, color)
        except Exception:
            _log('marker color')

    def feedback(self, event_id, vehicle_id, value):
        if event_id == self.feedback_event:
            self.piercing = value.get('gunPiercing', 1)

    def clear_colors(self, *unused):
        self.marker_targets.clear()
        for name in tuple(self.marker_names):
            self.panel.as_setGunMarkerColorS(name, 'normal')

    def target_changed(self, event):
        # Lock changes invalidate the previous collision, even before the next aim update.
        self.clear_colors()

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
        for marker_type, entity in list(self.marker_targets.items()):
            if entity is None:
                continue
            try:
                valid = entity.health > 0 and getattr(entity, 'isCrewActive', True) and BigWorld.entity(entity.id) is entity
            except Exception:
                valid = False
            if not valid:
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
        data = dict.fromkeys(_DATA_FIELDS, _NAN)
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
        try:
            ammo = self.panel.sessionProvider.shared.ammo
            if ammo is not None:
                data['total'] = _number(ammo.getGunReloadingState().getBaseValue())
        except Exception:
            _log('reload base time')
        if ammo is not None:
            try:
                # _AmmoSettings delegates to this getter: automatic fire is 0.
                settings = ammo.getGunSettings()
                data['burstTime'] = _number(settings.getClipInterval())
                if vehicle is not None:
                    data['fullReloadTime'] = self.full_reload_time(
                        vehicle.typeDescriptor.gun, settings.clip.size, data['total'], data['burstTime'])
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
                        break
            except Exception:
                _log('current shell')
        if self.geometry is not None:
            try:
                data.update(self.geometry.sample(self.panel, data['splash']))
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
            flash = self.panel.flashObject
            # Native initCrosshairs adds the wrappers directly; Timeline.name is read-only.
            for index in range(int(flash.numChildren)):
                try:
                    child = flash.getChildAt(index)
                    receive = getattr(child, 'as_whiteBladeData', None)
                    # An undefined GFx dynamic method may still be callable: require ACK.
                    if callable(receive) and receive(data) is True:
                        found = True
                except Exception:
                    _log('GFx child %d' % index)
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
                bus.removeListener(kind, self.target_changed, scope=scope)
            except Exception:
                _log('target event unsubscribe')
            self.target_bus = None
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
        result = original_color(panel, name, color, *args, **kwargs)
        if _active is not None and _active.panel is panel:
            if color == 'normal':
                _active.marker_names.discard(name)
            else:
                _active.marker_names.add(name)
        return result

    CrosshairPanelContainer._populate = populate
    CrosshairPanelContainer._dispose = dispose
    CrosshairPanelContainerMeta.as_setShotFlyTimesS = flights
    CrosshairPanelContainerMeta.as_setGunMarkerColorS = marker_color
    _installed = True


def fini():
    _stop()


init()
