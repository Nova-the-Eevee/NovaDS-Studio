-- Original DS / DS Lite: move Nova through a 512x512 world.
local speed = 105
function Start()
    Camera.follow("top", self.id)
    UI.print("bottom",1,1,"NOVA DS TILEMAP DEMO")
    UI.print("bottom",1,2,"TOP: CAMERA + PARALLAX")
end
function Update(dt)
    if Input.isDown("LEFT") then self.x = self.x - speed*dt end
    if Input.isDown("RIGHT") then self.x = self.x + speed*dt end
    if Input.isDown("UP") then self.y = self.y - speed*dt end
    if Input.isDown("DOWN") then self.y = self.y + speed*dt end
    if self.x < 0 then self.x = 0 end
    if self.x > 500 then self.x = 500 end
    if self.y < 0 then self.y = 0 end
    if self.y > 490 then self.y = 490 end
end
