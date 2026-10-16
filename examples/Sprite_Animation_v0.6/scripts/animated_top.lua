local speed = 110
local angle = 0

function Start()
    Camera.follow("top", self.id)
    UI.print("top", 0, 1, "D-PAD MOVE A SPIN B ZOOM")
end

function Update(dt)
    if Input.isDown("LEFT") then
        self.x = self.x - speed*dt
        self.flipX = true
    end
    if Input.isDown("RIGHT") then
        self.x = self.x + speed*dt
        self.flipX = false
    end
    if Input.isDown("UP") then self.y = self.y - speed*dt end
    if Input.isDown("DOWN") then self.y = self.y + speed*dt end
    if Input.isDown("A") then self.angle = self.angle + 190*dt end
    if Input.pressed("B") then
        self.scaleX = (self.scaleX == 1) and 1.8 or 1
        self.scaleY = self.scaleX
    end
    if Input.pressed("Y") then self.playing = not self.playing end
end
