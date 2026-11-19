# coding: utf-8
# SPDX-License-Identifier: GPL-3.0-or-later
"""Read-only SPG metric circle projection. Does not alter the native marker."""
import math
import BigWorld
import GUI
import Math
from AvatarInputHandler import aih_global_binding, gun_marker_ctrl
from aih_constants import CTRL_MODE_NAME


def finite(value):
    return not math.isnan(value) and not math.isinf(value)


def screen(point, width, height, scale):
    matrix = Math.Matrix()
    matrix.setTranslate(point)
    matrix = BigWorld.checkAndRecalculateIfPositionInExtremeProjection(matrix)
    transformed = BigWorld.makeWorldMatrix(width / height, matrix)
    p = transformed.applyV4Point(Math.Vector4(0., 0., 0., 1.))
    if p[3] <= 0 or not all(finite(v) for v in p):
        return None
    return ((p[0] / p[3] + 1.) * .5 * width / scale,
            (1. - p[1] / p[3]) * .5 * height / scale)


class Geometry(object):
    client = aih_global_binding.bindRO(aih_global_binding.BINDING_ID.CLIENT_SPG_GUN_MARKER_DATA_PROVIDER)
    server = aih_global_binding.bindRO(aih_global_binding.BINDING_ID.SERVER_SPG_GUN_MARKER_DATA_PROVIDER)

    def sample(self, panel, splash):
        empty = dict(height=float('nan'), splashPixels=float('nan'), splashRadiusX=float('nan'),
                     splashRadiusY=float('nan'), splashRotation=float('nan'), splashX=0., splashY=0.)
        player = BigWorld.player()
        if player is None or player.inputHandler.ctrlModeName not in (CTRL_MODE_NAME.STRATEGIC, CTRL_MODE_NAME.ARTY):
            return empty
        provider = self.server if gun_marker_ctrl.useServerGunMarker() else self.client
        if provider is None:
            return empty
        point = Math.Matrix(provider.positionMatrixProvider).translation
        camera = Math.Matrix(BigWorld.camera().invViewMatrix)
        empty['height'] = abs(camera.translation.y - point.y)
        if not finite(splash) or splash <= 0:
            return empty
        width, height = map(float, GUI.screenResolution())
        scale = float(panel.getScale())
        if not all(finite(v) and v > 0 for v in (width, height, scale)):
            return empty
        centre = screen(point, width, height, scale)
        ground_x = screen(point + Math.Vector3(1., 0., 0.) * splash, width, height, scale)
        ground_z = screen(point + Math.Vector3(0., 0., 1.) * splash, width, height, scale)
        if centre is None or ground_x is None or ground_z is None:
            return empty
        ex = (ground_x[0] - centre[0], ground_x[1] - centre[1])
        ez = (ground_z[0] - centre[0], ground_z[1] - centre[1])
        xx = ex[0] * ex[0] + ez[0] * ez[0]
        xy = ex[0] * ex[1] + ez[0] * ez[1]
        yy = ex[1] * ex[1] + ez[1] * ez[1]
        trace = xx + yy
        delta = math.sqrt(max(0., (xx - yy) * (xx - yy) + 4. * xy * xy))
        major = math.sqrt(max(0., (trace + delta) * .5))
        minor = math.sqrt(max(0., (trace - delta) * .5))
        angle = .5 * math.atan2(2. * xy, xx - yy)
        anchor = panel.sessionProvider.shared.crosshair.getScaledPosition()
        if finite(major) and finite(minor) and major > 0 and minor > 0:
            empty.update(splashPixels=major, splashRadiusX=major, splashRadiusY=minor,
                         splashRotation=angle * 180. / math.pi,
                         splashX=centre[0]-anchor[0], splashY=centre[1]-anchor[1])
        return empty
