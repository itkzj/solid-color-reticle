// SPDX-License-Identifier: GPL-3.0-or-later
package {
    import flash.display.DisplayObject;
    import flash.display.DisplayObjectContainer;
    import flash.geom.ColorTransform;
    import flash.utils.getQualifiedClassName;

    public final class WhiteBladeMarkers {
        private static const IDENTITY:ColorTransform = new ColorTransform();

        public static function apply(container:DisplayObjectContainer):void {
            if (!container) return;
            for (var i:int=0; i<container.numChildren; i++) {
                var node:DisplayObject = container.getChildAt(i);
                var kind:String = getQualifiedClassName(node);
                // Native labels set the fill. A parent tint would also recolor the outlines.
                if (kind=="GunMarkerSPGUI" || kind=="GunMarkerSPGDebugUI" || kind=="ArtyHitMarkerUI")
                    node.transform.colorTransform = IDENTITY;
            }
        }
    }
}
