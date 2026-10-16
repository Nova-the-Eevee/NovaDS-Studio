-- NovaDS Studio v0.9.3: REAL Lua controlling baked 3D clips
local fast = false
function Start()
    UI.clear("bottom")
    UI.print("bottom",1,1,"NOVADS 3D ANIMATION")
    UI.print("bottom",1,4,"A : PAUSE / RESUME")
    UI.print("bottom",1,6,"B : RESTART BOUNCE")
    UI.print("bottom",1,8,"X : SWITCH SPEED")
    UI.print("bottom",1,10,"Y : STOP / PLAY")
    UI.print("bottom",1,13,"LEFT: TRANSFORM KEYS")
    UI.print("bottom",1,15,"RIGHT: MESH FRAMES")
    self:playAnimation("Bounce")
end
function Update(dt)
    local morph=Scene.get(2)
    if Input.pressed("A") then
        if self.animationPlaying then
            self:pauseAnimation()
            morph:pauseAnimation()
        else
            self:resumeAnimation()
            morph:resumeAnimation()
        end
    end
    if Input.pressed("B") then self:restartAnimation() end
    if Input.pressed("X") then
        fast=not fast
        self.animationSpeed=fast and 2 or 1
        morph.animationSpeed=fast and 2 or 1
    end
    if Input.pressed("Y") then
        if self.animationPlaying then self:stopAnimation()
        else self:playAnimation("Bounce") end
    end
end
