# SPDX-License-Identifier: GPL-3.0-or-later
"""Generate the three mode-specific entry points from the shared adapter code."""

MODES = ('arcade', 'sniper', 'strategic')
METHODS='''
        private var whiteBlade:WhiteBladeHUD;
        private var previewSeeded:Boolean=false;
        private function hud():WhiteBladeHUD {
            if(!whiteBlade) { whiteBlade=new WhiteBladeHUD(ARTY); addChild(whiteBlade); }
            return whiteBlade;
        }
        private function clean(event:Event=null):void {
            var h:WhiteBladeHUD=hud();
            // Settings has no battle Python bridge. Seed only missing illustrative fields.
            if(!previewSeeded && parent && getQualifiedClassName(parent)=="AimSettings") {
                previewSeeded=true;
                h.seedPreview();
            }
            for(var i:int=0;i<numChildren;i++) {
                var child:DisplayObject=getChildAt(i);
                // Keep native special-mechanic indicators functional; hide only replaced art.
                if(child!=h && child!=cassetteMC && HIDE.indexOf(child.name)>=0)child.visible=false;
                // ponytail: the pinned strategic timeline has one direct Shape (the stock side arcs); recheck on a client update.
                if(ARTY && (child is Shape || child is ArtyIndicationScale || child is ArtyShotIndicatorsPanel)) {
                    child.visible=false;
                }
            }
            if(quickReloadingTimerTextField)quickReloadingTimerTextField.visible=false;
            HIDE_NATIVE_ZOOM
            if(h.parent!=this)addChild(h);
            if(ARTY)WhiteBladeMarkers.apply(parent);
            refreshStyle(h);
            syncCassette(h);
        }
        private function syncCassette(h:WhiteBladeHUD):void {
            if(cassetteMC) {
                // Native isCassette excludes special loaders; restore a previously hidden fallback.
                cassetteMC.visible=isCassette && h.clipGroups()>10;
                if(cassetteMC.visible) {
                    var bounds:Rectangle=cassetteMC.getBounds(cassetteMC);
                    cassetteMC.x=-(bounds.x+bounds.width/2)*cassetteMC.scaleX;
                    cassetteMC.y=h.clipCenterY()-(bounds.y+bounds.height/2)*cassetteMC.scaleY;
                }
            }
        }
        private function refreshStyle(h:WhiteBladeHUD):void {
            h.setStyle(centerType,centerAlpha,reloadingBarAlpha,healthBarAlpha,cassetteAlpha,reloadingTimeFieldAlpha);
        }
        override public function setCenterType(v:Number):void {super.setCenterType(v);refreshStyle(hud());}
        override public function setComponentsAlpha(net:Number,center:Number,reload:Number,hp:Number,clip:Number,time:Number,other:Number):void {
            super.setComponentsAlpha(net,center,reload,hp,clip,time,other);refreshStyle(hud());
        }
        override protected function updateReloadingState():void {
            super.updateReloadingState();
            // Native state and progress updates can re-show these before the next frame.
            if(reloadingAnimationMC)reloadingAnimationMC.visible=false;
            if(timerProgressTextField)timerProgressTextField.visible=false;
            if(timerCompleteTextField)timerCompleteTextField.visible=false;
        }
        override public function setReloadingState(v:String):void {super.setReloadingState(v);var h:WhiteBladeHUD=hud();h.setReloadState(v);h.refresh();}
        override public function setReloadingAsPercent(v:Number):void {super.setReloadingAsPercent(v);var h:WhiteBladeHUD=hud();h.setReloadPercent(v);h.refresh();}
        override public function setReloadingTime(v:Number):void {super.setReloadingTime(v);hud().setRemaining(v);}
        override public function setHealth(v:Number):void {super.setHealth(v);hud().setHealthRatio(v);}
        override public function setDistance(v:String):void {super.setDistance(v);var n:Array=v?v.match(/[0-9]+(?:[.,][0-9]+)?/):null;hud().setDistanceText(n?n[0]+" m":"");}
        override public function clearDistance(immediate:Boolean):void {super.clearDistance(immediate);hud().setDistanceText("");}
        override public function setZoom(v:String):void {super.setZoom(v);var n:Array=v?v.match(/[0-9]+(?:[.,][0-9]+)?/):null;HIDE_ZOOM_NOW hud().setZoomText(n?"\u00d7"+n[0]:"");}
        override public function setClipsParam(capacity:Number,burst:Number,type:int):void {
            super.setClipsParam(capacity,burst,type);
            var h:WhiteBladeHUD=hud();
            h.setClipParameters(capacity,burst);
            if(netSeparator)netSeparator.visible=false;
            syncCassette(h);
        }
        override public function setAmmoStock(total:uint,loaded:Number,state:String,reloaded:Boolean=false):void {super.setAmmoStock(total,loaded,state,reloaded);var h:WhiteBladeHUD=hud();h.setStock(total,loaded);h.refresh();}
        public function as_whiteBladeData(value:Object):Boolean {
            if(!value)return false;
            var h:WhiteBladeHUD=hud();
            h.applySample(value);
            if(value.hasOwnProperty("nativeRing") && value.hasOwnProperty("glowCross")) {
                var size:*=value.glowSize;
                if(!(size is Number) || !(size>=5 && size<=200) || size%5!=0) size=100;
                var distance:*=value.glowDistance;
                if(!(distance is Number) || !(distance>=0 && distance<=100) || distance%1!=0) distance=5;
                WhiteBladeMarkers.configure(parent,value.nativeRing===true,value.glowCross===true,size/100,distance/100);
            }
            h.refresh();return true;
        }
        public function as_whiteBladeAim(armor:Number,chance:Number,color:Number):Boolean {
            if(ARTY)return false;
            hud().setAim(armor,chance,color);return true;
        }
        override protected function onDispose():void {removeEventListener(Event.ENTER_FRAME,clean);super.onDispose();whiteBlade=null;}
'''


def render(mode):
    if mode not in MODES:
        raise ValueError("Unknown crosshair mode: " + mode)
    title = mode.title()
    old, base = f'Crosshair{title}UI', f'WhiteBlade{title}Base'
    arty = mode == 'strategic'
    body='package {\nimport flash.events.Event; import flash.display.DisplayObject; import flash.geom.Rectangle; import flash.utils.getQualifiedClassName;\nimport flash.display.Shape; import net.wg.gui.components.crosshairPanel.components.artyScale.ArtyIndicationScale;\nimport net.wg.gui.components.crosshairPanel.components.artyShot.ArtyShotIndicatorsPanel;\npublic class '+old+' extends '+base+' {\n'
    body+='private const ARTY:Boolean='+str(arty).lower()+';\n'
    body+='private const HIDE:Array=["timerProgressTextField","timerCompleteTextField","reloadTimeBlink","reloadingBar","reloadingAnimationMC","healthBarMC","centerMC","netMC","netSeparator","distance","averageDamage"];\n'
    body+='public function '+old+'(){super();addEventListener(Event.ENTER_FRAME,clean);}\n'
    hide_zoom = '            if(zoomTF)zoomTF.visible=false;\n' if mode == 'sniper' else ''
    return body + METHODS.replace('            HIDE_NATIVE_ZOOM\n', hide_zoom).replace('HIDE_ZOOM_NOW ', hide_zoom.strip() + ' ' if hide_zoom else '') + '\n}}\n'
