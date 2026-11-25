# SPDX-License-Identifier: GPL-3.0-or-later
"""Maintain the minimum dispersion marker providers during native battle views."""
from __future__ import absolute_import

import BigWorld


_providers = None
_INF = float('inf')
_NAN = float('nan')


def start():
    global _providers
    _providers = {}


def stop():
    global _providers
    _providers = None


def _minimum_diameter(player, marker):
    descriptor = player._PlayerAvatar__getDetailedVehicleDescriptor()
    # Native dispersion uses this multiplier even at rest.
    angle = descriptor.gun.shotDispersionAngle * player._PlayerAvatar__dispersionInfo[0]
    current = player.gunRotator.getCurShotDispersionAngles()[0]
    size = marker.size
    if 0 < angle < _INF and 0 < current < _INF and 0 < size < _INF:
        # Preserve the native shot distance when a collision or max range shortens it.
        return angle, size * angle / current
    return _NAN, _NAN


def install(log, add_hook, enabled):
    import Math
    from AvatarInputHandler import gun_marker_ctrl as ctrl
    from gui.Scaleform.daapi.view.battle.shared.crosshair import gm_components
    from gui.Scaleform.daapi.view.battle.shared.crosshair.gm_factory import _VIEW_ID

    collection = gm_components.GunMarkersComponents
    default = ctrl._DefaultGunMarkerController
    spg = ctrl._SPGGunMarkerController
    make = ctrl._GunMarkersDPFactory
    original_collection = collection.__init__
    original_default = default.update
    original_spg = spg.update
    primary = (ctrl._MARKER_TYPE.CLIENT, ctrl._MARKER_TYPE.SERVER)
    reference_type = object()  # Do not participate in native marker-type lookup.

    def create_collection(self, components):
        active = _providers
        if not enabled() or active is None:
            return original_collection(self, components)
        markers = tuple(components)
        providers, extra, seen = {}, [], set()
        try:
            for source in markers:
                view = source.getViewID()
                if view in seen or view not in (_VIEW_ID.ARCADE, _VIEW_ID.SNIPER, _VIEW_ID.STRATEGIC):
                    continue
                if source.getMarkerType() not in primary:
                    continue
                strategic = view == _VIEW_ID.STRATEGIC
                linkage = 'GunMarkerSPGUI' if strategic else 'GunMarkerUI'
                # The strategic view can also contain a separate artillery hit marker.
                if strategic and source.getViewSettings().linkage != linkage:
                    continue
                native = source._dataProvider
                if native is None:
                    continue
                key = id(native)
                if key not in providers:
                    provider = make._makeSPGProvider() if strategic else make._makeDefaultProvider()
                    provider.positionMatrixProvider = native.positionMatrixProvider
                    providers[key] = (native, provider)
                marker_class = gm_components.SPGGunMarkerComponent if strategic else gm_components.DefaultGunMarkerComponent
                extra.append(marker_class(reference_type, view, 'solidReticleMinimum' + source.getName(),
                                          linkage, providers[key][1], source.isActive()))
                seen.add(view)
        except Exception:
            log('minimum marker setup')
            providers.clear()
            extra[:] = []
        result = original_collection(self, markers + tuple(extra))
        active.clear()
        active.update(providers)
        return result

    def reference(controller):
        if enabled() and _providers is not None:
            pair = _providers.get(id(controller._dataProvider))
            if pair is not None:
                return pair[1]
        return None

    def update_default(self, markerType, gunMarkerInfo, supportMarkersInfo=None, relaxTime=-1.0):
        result = original_default(self, markerType, gunMarkerInfo, supportMarkersInfo, relaxTime)
        provider = reference(self)
        if provider is not None:
            try:
                _, diameter = _minimum_diameter(BigWorld.player(), gunMarkerInfo)
                if diameter > 0:
                    position = Math.createTranslationMatrix(gunMarkerInfo.position)
                    position = BigWorld.checkAndRecalculateIfPositionInExtremeProjection(position)
                    world = ctrl._makeWorldMatrix(position)
                    pixels = BigWorld.markerHelperScale(world, diameter) * self._DefaultGunMarkerController__screenRatio
                    provider.sizeConstraint = self._dataProvider.sizeConstraint
                    provider.updateSizes(pixels, 0.0, relaxTime, 0.0)
            except Exception:
                log('minimum marker projection')
        return result

    def update_spg(self, markerType, gunMarkerInfo, supportMarkersInfo, relaxTime):
        result = original_spg(self, markerType, gunMarkerInfo, supportMarkersInfo, relaxTime)
        provider = reference(self)
        if provider is not None:
            try:
                angle, diameter = _minimum_diameter(BigWorld.player(), gunMarkerInfo)
                if diameter > 0:
                    provider.setupConicDispersion(angle)
                    position, velocity, gravity = self._getCurrentShotInfo()
                    provider.update(position, velocity, gravity, diameter)
            except Exception:
                log('minimum strategic marker projection')
        return result

    add_hook(collection, '__init__', create_collection)
    add_hook(default, 'update', update_default)
    add_hook(spg, 'update', update_spg)
