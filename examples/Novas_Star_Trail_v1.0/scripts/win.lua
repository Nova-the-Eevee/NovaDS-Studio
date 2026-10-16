function Start()
    Camera3D.setPosition(0,1.5,5.0)
    Camera3D.setRotation(0,-7)
    UI.clear("bottom")
    UI.print("bottom",2,3,"CONGRATULATIONS!")
    UI.print("bottom",2,5,"YOU GOT ALL 3 CRYSTALS")
    UI.print("bottom",2,7,"THE GATE IS OPEN!")
    UI.print("bottom",2,10,"TIME: "..tostring(_G.StarTrailTime or 0).." sec")
    UI.print("bottom",2,15,"A / TOUCH: PLAY AGAIN")
    UI.print("bottom",2,18,"B: TITLE")
    UI.print("bottom",2,21,"NOVA WINS! :3")
end
function Update(dt)
    if Input.pressed("A") or UI.button("bottom",2,16,"[ REPLAY ]") then Scene.load("Level") end
    if Input.pressed("B") then Scene.load("Title") end
end
