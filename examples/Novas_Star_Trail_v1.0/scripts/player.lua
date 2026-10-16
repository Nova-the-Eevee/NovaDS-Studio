-- Player controller. No hardcoded 3D gameplay is required in main.c.
local collected = 0
local elapsed = 0
local seconds_drawn = -1
local message_frames = 0
local speed = 2.8
local jump_power = 5.7
local crystals = {[20]=true,[21]=true,[22]=true}

local function show_status(message)
    UI.print("bottom",1,12,"                            ")
    UI.print("bottom",1,12,message)
end
local function update_stars()
    UI.print("bottom",1,5,"CRYSTALS: "..collected.." / 3")
    UI.bar("bottom",1,7,21,collected,3)
end

function Start()
    collected = 0
    elapsed = 0
    seconds_drawn = -1
    message_frames = 0
    self.physics = true
    self.collider = true
    self.gravity = -13
    UI.clear("bottom")
    UI.print("bottom",1,1,"STAR TRAIL - THE MEADOW")
    UI.print("bottom",1,3,"D-PAD MOVE  A JUMP  B MENU")
    UI.print("bottom",1,9,"Y: RAYCAST DOWN")
    UI.print("bottom",1,17,"COLLECT GOLD CRYSTALS")
    UI.print("bottom",1,18,"THEN ENTER BLUE GATE")
    UI.print("bottom",1,20,"RED CUBES ARE DANGEROUS!")
    update_stars()
    show_status("GOOD LUCK, NOVA! :3")
    Camera3D.setRotation(0,-16)
end

function Update(dt)
    elapsed = elapsed + dt
    self.vx, self.vz = 0, 0
    if Input.isDown("LEFT") then self.vx = -speed end
    if Input.isDown("RIGHT") then self.vx = speed end
    if Input.isDown("UP") then self.vz = -speed end
    if Input.isDown("DOWN") then self.vz = speed end
    if Input.pressed("A") and self.grounded then self.vy = jump_power end
    if Input.pressed("B") then Scene.load("Title") end

    -- Third-person tracking. The camera looks downward from behind.
    Camera3D.setPosition(self.x,self.y+2.55,self.z+5.8)
    Camera3D.setRotation(0,-16)
    local seconds = math.floor(elapsed)
    if seconds ~= seconds_drawn then
        seconds_drawn = seconds
        UI.print("bottom",1,15,"TIME: "..seconds.." sec      ")
    end
    if message_frames > 0 then
        message_frames = message_frames - 1
        if message_frames == 0 then show_status("") end
    end
    if Input.pressed("Y") then
        local hit,dist=Physics3D.raycast(self.x,self.y,self.z,0,-1,0,8,self.id)
        if hit then show_status("RAY HIT OBJECT #"..hit.id)
        else show_status("RAY: NO HIT") end
        message_frames = 100
    end
    if self.y < -3 then
        Audio.play("ouch")
        Scene.load("Lose")
    end
end

function OnCollisionEnter(other)
    if crystals[other.id] and other.collider then
        other.collider = false
        other.visible = false
        collected = collected + 1
        Audio.play("collect")
        update_stars()
        show_status("CRYSTAL COLLECTED!")
        message_frames = 100
    elseif other.id == 30 then
        if collected >= 3 then
            _G.StarTrailTime = math.floor(elapsed)
            Audio.play("win")
            Scene.load("Win")
        else
            show_status("NEED ALL 3 CRYSTALS!")
            message_frames = 100
        end
    elseif other.id == 40 or other.id == 41 then
        Audio.play("ouch")
        Scene.load("Lose")
    end
end
