# coding: utf-8
# SPDX-License-Identifier: GPL-3.0-or-later
"""Read-only projection for the SPG footprint and horizontal gun limits."""
import math
import BigWorld
import GUI
import Math
from AvatarInputHandler import aih_global_binding, gun_marker_ctrl
from aih_constants import CTRL_MODE_NAME


_NAN = float('nan')
_EMPTY_TRAVERSE = (_NAN,) * 5
_SPG_MODES = (CTRL_MODE_NAME.STRATEGIC, CTRL_MODE_NAME.ARTY)


def finite(value):
    return not math.isnan(value) and not math.isinf(value)


def screen(point, width, height):
    matrix = Math.Matrix()
    matrix.setTranslate(point)
    matrix = BigWorld.checkAndRecalculateIfPositionInExtremeProjection(matrix)
    transformed = BigWorld.makeWorldMatrix(width / height, matrix)
    p = transformed.applyV4Point(Math.Vector4(0., 0., 0., 1.))
    if p[3] <= 0 or not all(finite(v) for v in p):
        return None
    return ((p[0] / p[3] + 1.) * .5 * width,
            (1. - p[1] / p[3]) * .5 * height)


def _spg_traverse_axis(rotator, point, width, height, scale, centre):
    if centre is None:
        return None
    origin, velocity = rotator.getCurShotPosition()
    speed = math.hypot(velocity.x, velocity.z)
    if not finite(speed) or speed <= 0:
        return None
    distance = math.hypot(point.x - origin.x, point.z - origin.z)
    shot_x, shot_z = velocity.x / speed, velocity.z / speed
    # Project the local forward and lateral ground directions at the aim marker.
    forward = screen(point + Math.Vector3(shot_x, 0., shot_z), width, height)
    lateral = screen(point + Math.Vector3(shot_z, 0., -shot_x), width, height)
    if forward is None or lateral is None:
        return None
    dx, dy = forward[0] - centre[0], forward[1] - centre[1]
    length = math.hypot(dx, dy)
    if not finite(length) or length <= 1e-6 * scale:
        return None
    # Use only the lateral component perpendicular to the projected shot line.
    pixels_per_metre = abs(-dy * (lateral[0] - centre[0]) + dx * (lateral[1] - centre[1])) / length
    units_per_radian = distance * pixels_per_metre / scale
    if not finite(units_per_radian) or units_per_radian <= 0:
        return None
    return math.degrees(math.atan2(dx, -dy)), units_per_radian


def _viewport(panel):
    width, height = map(float, GUI.screenResolution())
    return width, height, float(panel.getScale())


def _traverse(panel, vehicle, player, mode, point, projection):
    empty = _EMPTY_TRAVERSE
    if vehicle is None or vehicle.health <= 0:
        return empty
    descriptor = vehicle.typeDescriptor
    if descriptor.gun.turretYawLimits is None:
        return empty
    if player is None or player.getVehicleAttached() is not vehicle:
        return empty
    if mode not in (CTRL_MODE_NAME.ARCADE, CTRL_MODE_NAME.SNIPER) + _SPG_MODES:
        return empty
    rotator = player.gunRotator
    limits = rotator._VehicleGunRotator__getTurretYawLimits()
    if limits is None:
        return empty
    left, right = limits
    if not (finite(left) and finite(right) and left <= right):
        return empty
    yaw = rotator.turretYaw
    if not finite(yaw):
        return empty
    half_span = (right - left) * .5
    # Unwrap about the actual midpoint, including asymmetric and rear-facing limits.
    relative = (yaw - (left + half_span) + math.pi) % (2 * math.pi) - math.pi
    # Use the last 0.5 degrees, capped for very narrow arcs, as the red warning zone.
    warning = min(math.radians(.5), half_span * .1)
    fade_span = half_span - warning

    width, height, scale = projection[0] if projection is not None else _viewport(panel)
    if not all(finite(v) and v > 0 for v in (width, scale)):
        return empty
    scale = max(1., scale)
    rotation = 0.
    # Let the viewport clip the arrows naturally even when the aim centre is offset.
    units_per_radian = width / (scale * math.pi)
    if mode in _SPG_MODES:
        if point is None or not finite(height) or height <= 0:
            return empty
        centre = projection[1] if projection is not None else screen(point, width, height)
        axis = _spg_traverse_axis(rotator, point, width, height, scale, centre)
        if axis is None:
            return empty
        rotation, units_per_radian = axis
    positions = []
    ratios = []
    for side, distance in ((-1., half_span + relative), (1., half_span - relative)):
        offset = 0. if distance <= 1e-9 else distance * units_per_radian
        positions.append(side * offset)
        # Green from the midpoint onward, also when the native limits coincide.
        if distance >= half_span:
            ratio = 1.
        elif distance <= warning:
            ratio = 0.
        else:
            ratio = (distance - warning) / fade_span
        ratios.append(ratio)
    return positions[0], positions[1], ratios[0], ratios[1], rotation


class Geometry(object):
    client = aih_global_binding.bindRO(aih_global_binding.BINDING_ID.CLIENT_SPG_GUN_MARKER_DATA_PROVIDER)
    server = aih_global_binding.bindRO(aih_global_binding.BINDING_ID.SERVER_SPG_GUN_MARKER_DATA_PROVIDER)

    def sample(self, panel, splash, vehicle, log):
        data = dict(height=_NAN, splashRadiusX=_NAN, splashRadiusY=_NAN,
                    splashRotation=_NAN, splashX=0., splashY=0.)
        player = BigWorld.player()
        mode = player.inputHandler.ctrlModeName if player is not None else None
        point = projection = None
        if mode in _SPG_MODES:
            try:
                provider = self.server if gun_marker_ctrl.useServerGunMarker() else self.client
                if provider is not None:
                    point = Math.Matrix(provider.positionMatrixProvider).translation
                if point is not None and finite(splash) and splash > 0:
                    viewport = _viewport(panel)
                    width, height, scale = viewport
                    if all(finite(v) and v > 0 for v in viewport):
                        # Share the unscaled centre. Traverse caps its UI scale at a minimum of one.
                        centre = screen(point, width, height)
                        projection = viewport, centre
                        if centre is not None:
                            self._footprint(data, panel, point, splash, width, height, scale, centre)
            except Exception:
                log('geometry sample')
            if point is not None:
                try:
                    camera = Math.Matrix(BigWorld.camera().invViewMatrix)
                    data['height'] = abs(camera.translation.y - point.y)
                except Exception:
                    log('camera height')
        try:
            return data, _traverse(panel, vehicle, player, mode, point, projection)
        except Exception:
            log('gun traverse')
            return data, _EMPTY_TRAVERSE

    def _footprint(self, data, panel, point, splash, width, height, scale, centre):
        ground_x = screen(point + Math.Vector3(1., 0., 0.) * splash, width, height)
        ground_z = screen(point + Math.Vector3(0., 0., 1.) * splash, width, height)
        if ground_x is None or ground_z is None:
            return
        ex = ((ground_x[0] - centre[0]) / scale, (ground_x[1] - centre[1]) / scale)
        ez = ((ground_z[0] - centre[0]) / scale, (ground_z[1] - centre[1]) / scale)
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
            data.update(splashRadiusX=major, splashRadiusY=minor,
                        splashRotation=angle * 180. / math.pi,
                        splashX=centre[0] / scale - anchor[0], splashY=centre[1] / scale - anchor[1])
