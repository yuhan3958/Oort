# Function: main_loop
execute if score tick_counter oort_vars matches ..4 run function oort_example:src/tick/if_body_1
execute if score tick_counter oort_vars matches 5 run function oort_example:src/tick/if_body_2
execute if score anc_clear oort_vars matches 1 run function oort_example:src/tick/if_body_3