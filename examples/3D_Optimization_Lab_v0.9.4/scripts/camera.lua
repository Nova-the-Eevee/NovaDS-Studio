-- First-person-ish camera demonstration. D-pad moves camera on XZ plane.
local cx,cy,cz=0,0,6.3
local yaw,pitch=0,0
function Start()
  Camera3D.setPosition(cx,cy,cz)
  Camera3D.setRotation(yaw,pitch)
end
function Update(dt)
  local speed=2.4*dt
  if Input.isDown("LEFT") then cx=cx-speed end
  if Input.isDown("RIGHT") then cx=cx+speed end
  if Input.isDown("UP") then cz=cz-speed end
  if Input.isDown("DOWN") then cz=cz+speed end
  if Input.isDown("L") then yaw=yaw-55*dt end
  if Input.isDown("R") then yaw=yaw+55*dt end
  cx=math.max(-4,math.min(4,cx))
  cz=math.max(2,math.min(12,cz))
  Camera3D.setPosition(cx,cy,cz)
  Camera3D.setRotation(yaw,pitch)
  if Input.pressed("A") then self.visible=not self.visible end
end
