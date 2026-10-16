-- Title screen, controlled entirely by Lua.
function Start()
    Camera3D.setPosition(0,1.5,5.0)
    Camera3D.setRotation(0,-7)
    UI.clear("bottom")
    UI.print("bottom",2,2,"NOVA'S STAR TRAIL")
    UI.print("bottom",2,4,"A COMPLETE 3D MINI-GAME")
    UI.print("bottom",2,7,"COLLECT 3 GOLD STARS")
    UI.print("bottom",2,8,"AVOID RED HAZARDS")
    UI.print("bottom",2,9,"REACH THE BLUE GATE")
    UI.print("bottom",2,12,"D-PAD: MOVE / A: JUMP")
    UI.print("bottom",2,14,"Y: RAY TEST")
    UI.print("bottom",2,18,"PRESS A TO START")
    UI.print("bottom",2,21,"Made with NovaDS v1.0")
end
function Update(dt)
    if Input.pressed("A") or UI.button("bottom",2,19,"[ TOUCH TO PLAY ]") then
        Audio.play("start")
        Scene.load("Level")
    end
end
