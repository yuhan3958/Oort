# Event: on load
scoreboard objectives add oort_vars dummy
scoreboard players set ready oort_vars 0
function oort_example:src/load/setup
scoreboard players set tick_counter oort_vars 0