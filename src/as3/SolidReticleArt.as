// SPDX-License-Identifier: GPL-3.0-or-later
package {
    import flash.display.BitmapData;
    import flash.display.CapsStyle;
    import flash.display.Graphics;
    import flash.display.JointStyle;
    import flash.display.LineScaleMode;
    import flash.geom.Matrix;

    public final class SolidReticleArt {
        public static const WHITE:uint=0xF7FAFF, GREEN:uint=0x7FFF36;
        private static const BACK:uint=0x10181E;
        private static const RADIUS:Number=256;
        private static const TICKS:int=24;

        public static function ringProgress(progress:Number,solid:Boolean):Number {
            return solid?progress:Math.ceil(progress*TICKS);
        }

        public static function ring(g:Graphics, progress:Number, solid:Boolean, bold:Boolean):void {
            g.clear();
            var ink:Number=bold?8:4;
            var ticks:Number=ringProgress(progress,solid);
            for (var pass:int=0;pass<2;pass++) {
                if (solid) {
                    if (!pass || progress<=0 || progress>=1) {
                        stroke(g,ink+(pass?0:2),pass?(progress>=1?GREEN:WHITE):BACK,LineScaleMode.NONE);
                        g.drawCircle(0,0,RADIUS);
                    } else {
                        stroke(g,ink,WHITE,LineScaleMode.NONE);
                        arc(g,progress,1);
                        stroke(g,ink+2,BACK,LineScaleMode.NONE);
                        arc(g,0,progress);
                        stroke(g,ink,GREEN,LineScaleMode.NONE);
                        arc(g,0,progress);
                    }
                } else {
                    for (var i:int=0;i<TICKS;i++) {
                        var angle:Number=i*Math.PI*2/TICKS-Math.PI/2;
                        var x:Number=Math.cos(angle), y:Number=Math.sin(angle);
                        stroke(g,ink+(pass?0:2),pass?(i<ticks?GREEN:WHITE):BACK,LineScaleMode.NONE);
                        segment(g,x*206,y*206,x*RADIUS,y*RADIUS);
                    }
                }
            }
        }

        private static function arc(g:Graphics,from:Number,to:Number):void {
            var angle:Number=from*2*Math.PI-Math.PI/2;
            var steps:int=Math.ceil((to-from)*8);
            var step:Number=(to-from)*2*Math.PI/steps;
            var controlRadius:Number=RADIUS/Math.cos(step/2);
            g.moveTo(RADIUS*Math.cos(angle),RADIUS*Math.sin(angle));
            for (var i:int=0;i<steps;i++) {
                var middle:Number=angle+step/2;
                angle+=step;
                g.curveTo(controlRadius*Math.cos(middle),controlRadius*Math.sin(middle),
                    RADIUS*Math.cos(angle),RADIUS*Math.sin(angle));
            }
        }

        private static const BLADE_GAP:Number=6.75;
        private static const BLADE_LENGTH:Number=81;
        private static const BLADE_HALF_HEIGHT:int=14;
        private static const BLADE_SAMPLES:int=4;
        // V19's placed blade reaches about 239.4 local units from the centre.
        private static const BLADE_RADIUS:Number=239.4;
        private static var bladeTexture:BitmapData;

        public static function gun(g:Graphics, type:Number, color:uint):void {
            g.clear();
            if (!isFinite(type)||type!=int(type)||type<0||type>=15) return;
            var group:int=int(type/3);
            for (var pass:int=0;pass<2;pass++) {
                var ink:uint=pass?color:BACK;
                var width:Number=group==0?2.5:group==3?1.25:2;
                stroke(g,width+(pass?0:2),ink,LineScaleMode.NORMAL);
                if (group==0) {
                    g.moveTo(-8.75,15); g.lineTo(0,0); g.lineTo(8.75,15);
                } else if (group==1) {
                    if (pass) g.lineStyle();
                    else stroke(g,2,ink,LineScaleMode.NORMAL);
                    g.beginFill(ink);
                    g.moveTo(-12,-1);g.lineTo(-1,-1);g.lineTo(-1,-12);g.lineTo(1,-12);
                    g.lineTo(1,-1);g.lineTo(12,-1);g.lineTo(12,1);g.lineTo(1,1);
                    g.lineTo(1,12);g.lineTo(-1,12);g.lineTo(-1,1);g.lineTo(-12,1);g.lineTo(-12,-1);
                    g.endFill();
                } else if (group==2) {
                    dot(g,pass?3:4,ink);
                } else if (group==3) {
                    g.drawCircle(0,0,6.5);
                } else {
                    segment(g,-15,0,-7,0); segment(g,7,0,15,0);
                    segment(g,0,-15,0,-7); segment(g,0,7,0,15);
                }
            }
        }

        public static function drawBlades(g:Graphics):void {
            if (!bladeTexture) bladeTexture=makeBlade();
            var image:BitmapData=bladeTexture;
            var scale:Number=BLADE_RADIUS*BLADE_SAMPLES/image.width;
            var length:Number=BLADE_RADIUS;
            var half:Number=BLADE_HALF_HEIGHT*scale;
            for (var x:int=-1;x<=1;x+=2) {
                for (var y:int=-1;y<=1;y+=2) {
                    var dx:Number=x*Math.SQRT1_2, dy:Number=y*Math.SQRT1_2;
                    var matrix:Matrix=new Matrix(dx*scale/BLADE_SAMPLES,dy*scale/BLADE_SAMPLES,
                        -dy*scale/BLADE_SAMPLES,dx*scale/BLADE_SAMPLES,dy*half,-dx*half);
                    g.beginBitmapFill(image,matrix,false,true);
                    g.moveTo(dy*half,-dx*half);
                    g.lineTo(dx*length+dy*half,dy*length-dx*half);
                    g.lineTo(dx*length-dy*half,dy*length+dx*half);
                    g.lineTo(-dy*half,dx*half);
                    g.lineTo(dy*half,-dx*half);
                    g.endFill();
                }
            }
        }

        private static function makeBlade():BitmapData {
            // Historical pointed-spindle design: narrow spine, inner highlight and a separate soft halo.
            var image:BitmapData=new BitmapData(Math.ceil((BLADE_GAP+BLADE_LENGTH)*BLADE_SAMPLES),
                BLADE_HALF_HEIGHT*2*BLADE_SAMPLES,true,0);
            var haloRows:Array=[], coreRows:Array=[];
            for (var row:int=0;row<image.height;row++) {
                var offset:Number=(row+.5)/BLADE_SAMPLES-BLADE_HALF_HEIGHT;
                haloRows[row]=.19*gaussian(offset/3.7)+.27*gaussian(offset/1.65);
                coreRows[row]=gaussian(offset/.235);
            }
            image.lock();
            for (var x:int=0;x<image.width;x++) {
                var along:Number=(x+.5)/BLADE_SAMPLES;
                var distance:Number=along-BLADE_GAP;
                var q:Number=Math.max(0,Math.min(1,distance/BLADE_LENGTH));
                var envelope:Number=haloEnvelope(distance);
                var innerBlend:Number=smoothstep((12-distance)/8);
                if (innerBlend>0) {
                    var total:Number=0, weight:Number=0;
                    for (var tap:int=-20;tap<=20;tap++) {
                        var kernel:Number=gaussian(tap/5);
                        total+=kernel*haloEnvelope(distance+tap/2);
                        weight+=kernel;
                    }
                    envelope+=innerBlend*(total/weight-envelope);
                }
                var width:Number=q<.13?1.1*q/.13:q<.26?1.1-.1*(q-.13)/.13:
                    q<.65?1-.57*(q-.26)/.39:.43*(1-q)/.35;
                var highlight:Number=.98*gaussian((q-.15)/.105);
                for (var y:int=0;y<image.height;y++) {
                    var across:Number=(y+.5)/BLADE_SAMPLES-BLADE_HALF_HEIGHT;
                    var clearance:Number=smoothstep((Math.sqrt(along*along+across*across)-4.44)/2.22);
                    var glow:Number=haloRows[y]*envelope*clearance;
                    var body:Number=0, core:Number=0;
                    if (distance>=0 && distance<=BLADE_LENGTH) {
                        body=.8*Math.max(0,Math.min(1,(width-Math.abs(across))*BLADE_SAMPLES+.5))*(1-.73*q);
                        core=highlight*coreRows[y];
                    }
                    var light:Number=glow+body;
                    var energy:Number=light+core;
                    var alpha:int=Math.round(Math.min(1,energy)*255);
                    if (alpha>0) {
                        // Gray controls the blend from the probability hue to the warm highlight.
                        var gray:int=Math.round(core/energy*255);
                        image.setPixel32(x,y,(alpha<<24)|(gray<<16)|(gray<<8)|gray);
                    }
                }
            }
            image.unlock();
            return image;
        }

        private static function haloEnvelope(distance:Number):Number {
            if (distance<=0 || distance>=BLADE_LENGTH) return 0;
            var q:Number=distance/BLADE_LENGTH;
            return Math.pow(Math.sin(Math.PI*q),.46)*Math.exp(-1.85*q);
        }

        private static function gaussian(value:Number):Number {
            return Math.exp(-.5*value*value);
        }

        private static function smoothstep(value:Number):Number {
            var t:Number=Math.max(0,Math.min(1,value));
            return t*t*(3-2*t);
        }

        public static function point(g:Graphics, color:uint):void {
            g.clear();
            dot(g,5.5,BACK);
            dot(g,4,color);
        }

        private static function dot(g:Graphics, radius:Number, color:uint):void {
            g.lineStyle();g.beginFill(color);g.drawCircle(0,0,radius);g.endFill();
        }

        private static function stroke(g:Graphics,width:Number,color:uint,scale:String):void {
            g.lineStyle(width,color,1,false,scale,CapsStyle.ROUND,JointStyle.ROUND);
        }

        private static function segment(g:Graphics,x0:Number,y0:Number,x1:Number,y1:Number):void {
            g.moveTo(x0,y0);g.lineTo(x1,y1);
        }
    }
}
