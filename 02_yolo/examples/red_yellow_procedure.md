# Experiment: Red Yellow Box Demo

## Step 1
- id: pick_red
- action: PICK_RED
- object: red_box
- instruction: Pick up the red box.
- warning: Pick up the red box first.
- confirmation_frames: 3

## Step 2
- id: manipulate_red
- action: MANIPULATE_RED
- object: red_box
- instruction: Manipulate the red box.
- warning: Manipulate the red box before placing it.
- confirmation_frames: 3

## Step 3
- id: place_red
- action: PLACE_RED
- object: red_box
- instruction: Place the red box back.
- warning: Place the red box after manipulating it.
- confirmation_frames: 3

## Step 4
- id: pick_yellow
- action: PICK_YELLOW
- object: yellow_box
- instruction: Pick up the yellow box.
- warning: Complete the red box steps first.
- confirmation_frames: 3

## Step 5
- id: place_yellow
- action: PLACE_YELLOW
- object: yellow_box
- instruction: Place the yellow box back.
- warning: Place the yellow box back.
- confirmation_frames: 3
