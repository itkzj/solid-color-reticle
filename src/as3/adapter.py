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
                if(!isFinite(h.data.maxHealth))h.data.maxHealth=1800;
                if(!isFinite(h.data.health))h.data.health=Math.round(h.data.healthRatio*h.data.maxHealth);
                if(!isFinite(h.data.total))h.data.total=13.72;
                if(!isFinite(h.data.burstTime))h.data.burstTime=2.5;
                if(!isFinite(h.data.penetration))h.data.penetration=258;
                if(!h.data.shell)h.data.shell="AP";
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
            if(h.data.arty)WhiteBladeMarkers.apply(parent);
            refreshStyle();
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
        private function refreshStyle():void {
            var h:WhiteBladeHUD=hud();
            h.data.centerType=centerType;h.data.centerOpacity=centerAlpha;
            h.data.reloadOpacity=reloadingBarAlpha;h.data.healthOpacity=healthBarAlpha;
            h.data.clipOpacity=cassetteAlpha;h.data.timeOpacity=reloadingTimeFieldAlpha;
            h.refresh();
        }
        override public function setCenterType(v:Number):void {super.setCenterType(v);refreshStyle();}
        override public function setComponentsAlpha(net:Number,center:Number,reload:Number,hp:Number,clip:Number,time:Number,other:Number):void {
            super.setComponentsAlpha(net,center,reload,hp,clip,time,other);refreshStyle();
        }
        override protected function updateReloadingState():void {
            super.updateReloadingState();
            // Native state and progress updates can re-show these before the next frame.
            if(reloadingAnimationMC)reloadingAnimationMC.visible=false;
            if(timerProgressTextField)timerProgressTextField.visible=false;
            if(timerCompleteTextField)timerCompleteTextField.visible=false;
        }
        override public function setReloadingState(v:String):void {super.setReloadingState(v);hud().setReloadState(v);hud().refresh();}
        override public function setReloadingAsPercent(v:Number):void {super.setReloadingAsPercent(v);hud().setReloadPercent(v);hud().refresh();}
        override public function setReloadingTime(v:Number):void {super.setReloadingTime(v);hud().data.remaining=isFinite(v)?Math.max(0,v):NaN;hud().refresh();}
        override public function setHealth(v:Number):void {super.setHealth(v);hud().data.healthRatio=v;if(isFinite(hud().data.maxHealth))hud().data.health=Math.round(v*hud().data.maxHealth);hud().refresh();}
        override public function setDistance(v:String):void {super.setDistance(v);var n:Array=v?v.match(/[0-9]+(?:[.,][0-9]+)?/):null;hud().data.distance=n?n[0]+" m":"";hud().refresh();}
        override public function clearDistance(immediate:Boolean):void {super.clearDistance(immediate);hud().data.distance="";hud().refresh();}
        override public function setZoom(v:String):void {super.setZoom(v);var n:Array=v?v.match(/[0-9]+(?:[.,][0-9]+)?/):null;hud().data.zoom=n?"\u00d7"+n[0]:"";HIDE_ZOOM_NOW hud().refresh();}
        override public function setClipsParam(capacity:Number,burst:Number,type:int):void {
            super.setClipsParam(capacity,burst,type);
            var h:WhiteBladeHUD=hud();
            h.data.capacity=Math.max(1,capacity);
            h.data.burstSize=Math.max(1,burst);
            h.refresh();
            if(netSeparator)netSeparator.visible=false;
            syncCassette(h);
        }
        override public function setAmmoStock(total:uint,loaded:Number,state:String,reloaded:Boolean=false):void {super.setAmmoStock(total,loaded,state,reloaded);hud().setStock(total,loaded);hud().refresh();}
        private const numberFields:Array=["health","maxHealth","total","burstTime","height","splashRadiusX","splashRadiusY","splashRotation","splashX","splashY","flight","penetration","aimArmor","aimChance","aimColor","splash","traverseLeft","traverseRight","traverseLeftRatio","traverseRightRatio","traverseRotation"];
        public function as_whiteBladeData(value:Object):Boolean {
            if(!value)return false;
            var h:WhiteBladeHUD=hud();
            var d:Object=h.data;
            for each(var k:String in numberFields)
                if(value.hasOwnProperty(k))d[k]=Number(value[k]);
            if(value.hasOwnProperty("shell"))d.shell=String(value.shell);
            if(value.readyText is String && value.readyText.length>0)d.readyText=value.readyText;
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
