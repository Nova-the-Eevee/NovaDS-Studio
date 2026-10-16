local rotation_speed = 55
local elapsed = 0

function Update(dt)
    elapsed = elapsed + dt
    self.angle = (self.angle + rotation_speed * dt) % 360
    if Input.isDown("Y") then
        self.angle = self.angle + 140 * dt
    end
end
