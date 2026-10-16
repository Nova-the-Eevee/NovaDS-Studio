local t = 0
function Start()
    UI.print("bottom", 0, 1, "SPRITE AFFINE + LUA ANIMATION")
    UI.print("bottom", 0, 21, "Y PAUSES TOP ANIMATION")
end
function Update(dt)
    t=t+dt
    self.angle = math.sin(t * 2)*55
    self.scaleX = 1.4 + 0.25*math.sin(t * 3)
    self.scaleY = 1.4 + 0.25*math.cos(t * 3)
    self.flipY = math.sin(t*1.2) > 0.8
end
