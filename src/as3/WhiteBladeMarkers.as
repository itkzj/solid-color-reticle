// SPDX-License-Identifier: GPL-3.0-or-later
package {
    import flash.display.DisplayObjectContainer;
    import net.wg.gui.components.crosshairPanel.components.gunMarker.GunMarker;

    public final class WhiteBladeMarkers {
        public static function configure(container:DisplayObjectContainer, nativeRing:Boolean,
                                         glowCross:Boolean, glowScale:Number, glowDistance:Number):void {
            if (!container) return;
            for (var i:int=0; i<container.numChildren; i++) {
                var node:Object=container.getChildAt(i);
                var gun:GunMarker=node as GunMarker;
                if (gun) {
                    var tag:Object=gun.gunTag;
                    if (node.name.indexOf("solidReticleMinimum")!=0 && tag && "setWhiteBladeGlow" in tag) {
                        tag.setWhiteBladeGlow(glowCross,glowScale,glowDistance);
                    }
                    var radius:DisplayObjectContainer=gun.radiusMC as DisplayObjectContainer;
                    if (!radius) continue;
                    for (var j:int=0; j<radius.numChildren; j++) {
                        var mixing:Object=radius.getChildAt(j);
                        if ("setWhiteBladeNativeRing" in mixing) mixing.setWhiteBladeNativeRing(nativeRing);
                    }
                } else if ("setWhiteBladeNativeRing" in node) {
                    node.setWhiteBladeNativeRing(nativeRing);
                }
            }
        }

        public static function apply(container:DisplayObjectContainer):void {
            if (!container) return;
            for (var i:int=0; i<container.numChildren; i++) {
                var node:Object = container.getChildAt(i);
                if ("whiteBladeTint" in node) node.whiteBladeTint();
            }
        }
    }
}
