-- UEVR's inactivity clock counts actions, not tracked controller movement.
-- Keep tracked weapons enabled throughout a normal play session (24 hours).
uevr.params.vr.set_mod_value('VR_MotionControlsInactivityTimer', '86400.0')
uevr.params.functions.log_info('[Crisol Sense] Inactivity timer: ' .. tostring(uevr.params.vr:get_mod_value('VR_MotionControlsInactivityTimer')))
