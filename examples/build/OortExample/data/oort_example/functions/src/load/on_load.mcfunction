# Event: on load
scoreboard objectives add oort_vars dummy
function oort_example:src/load/setup
scoreboard players set tick_counter oort_vars 0
scoreboard players set anc_clear oort_vars 0