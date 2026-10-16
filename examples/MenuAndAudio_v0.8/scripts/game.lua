local elapsed=0
function Start()
    elapsed=0
    UI.clear("bottom")
    UI.print("bottom",1,2,"GAME - MOVE WITH D-PAD")
    UI.print("bottom",1,3,"B: BACK TO MENU")
end
function Update(dt)
    elapsed=elapsed+dt
    local speed=75
    if Input.isDown("LEFT") then self.x=self.x-speed*dt end
    if Input.isDown("RIGHT") then self.x=self.x+speed*dt end
    if Input.isDown("UP") then self.y=self.y-speed*dt end
    if Input.isDown("DOWN") then self.y=self.y+speed*dt end
    UI.bar("bottom",2,6,20,math.min(10,elapsed),10)
    if Input.pressed("B") then
        Audio.play("select",100,64,false)
        Scene.load("Menu")
    end
end
