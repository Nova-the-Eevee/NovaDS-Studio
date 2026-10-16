-- NovaDS v0.5 hardware BG + UI example.
local timer = 0
local speed = 80

function Start()
    UI.print("top", 1, 1, "NOVADS v0.5")
    UI.print("bottom", 1, 1, "AFFINE + LUA")
    UI.print("bottom", 1, 22, "D-PAD MOVE / A TILT")
end

function Update(dt)
    timer = timer + dt
    if Input.isDown("LEFT") then self.x = self.x - speed * dt end
    if Input.isDown("RIGHT") then self.x = self.x + speed * dt end
    if Input.isDown("UP") then self.y = self.y - speed * dt end
    if Input.isDown("DOWN") then self.y = self.y + speed * dt end

    Background.scroll("top", math.floor(timer * 12), 0)
    Background.scroll("bottom", math.floor(timer * 5), 0)
    if Input.isDown("A") then
        Background.transform("bottom", math.sin(timer * 2) * 14, 1.15)
    else
        Background.transform("bottom", 0, 1)
    end
end
