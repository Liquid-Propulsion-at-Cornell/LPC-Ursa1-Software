local mb = require("Modbus")

local pos_pin = 0
local neg_pin = 1
local res_ind = 8
local settle = 0
local celsius = 1
local farenheit = 2

function configure_thermocouple(ppin, npin, rind, set, temp)
    local pos_name = "AIN" .. ppin
    local neg_name = "AIN" .. ppin .. "_NEGATIVE_CH"
    mb.writeName(neg_name, npin)
    mb.writeName(pos_name .. "_RANGE", 0.1)
    mb.writeName(pos_name .. "_RESOLUTION_INDEX", rind)
    mb.writeName(pos_name .. "_SETTLING_US", set)
    mb.writeName(pos_name .. "_EF_INDEX", 22)
    mb.writeName(pos_name .. "_EF_CONFIG_A", temp)
end

function configure_transducer()

configure_thermocouple(pos_pin, neg_pin, res_ind, settle, celsius)

while(true)
    local tempC = mb.readName(pos_name .. "_EF_READ_A")
    print("Temperature (C): ", tempC)
end