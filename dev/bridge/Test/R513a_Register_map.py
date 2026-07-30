"""Core register map for supplying the R513A1505 HMI.

Derived from HMI_R513a1505.pdf:
- Tag Editor: PDF pages 21-29
- Base Screen 1 (Home / Monitor): PDF pages 30-33
- Alarm Log Settings: PDF page 5

The fourth register tuple field is the logger/plotter visual flag, not a
read/write flag. It is False here because this map is intended for HMI supply.
"""

PLC_CONFIGS = [
    {
        "name": "p1",
        "ip": "192.168.1.2",
        "device": "FF",
        "endian": "0",
        "registers": [
            # Home screen data values.
            ("Tank_Probe_Fahr_F", "D0054", "F"),
            ("Cond_LWT_Fahr_F", "D0056", "F"),
            ("Cond_EWT_Fahr_F", "D0058", "F"),
            ("AMB_Fahr_F", "D0062", "F"),
            ("UNUSED_Fahr_F", "D0068", "F"),
            ("Cond_LWT_Setpoint_F", "D0280", "F"),
            ("Heatcall_status", "D1300", "W"),
            ("HGBV_OPSS", "D1301", "W"),
            ("AMB_EvapEWT", "D1302", "W"),
            ("Tank_Target_HMI_F", "D1320", "F"),
            ("Demand_Mode_Display", "D1350", "W"),
            ("Cond_Flow_F", "D3826", "F"),

            # HMI alarm-log source words.
            ("Alarm_Register_1", "D3500", "W"),
            ("Alarm_Register_2", "D3501", "W"),
            ("Alarm_Register_3", "D3502", "W"),

            # Home-screen state and visibility conditions.
            ("Cycle_Status", "M0002", "B"),
            ("AS_WS_Config", "M0003", "B"),
            ("HGBV_Config", "M0004", "B"),
            ("SinglePass_Config", "M0005", "B"),
            ("Demand_Mode", "M0006", "B"),
            ("Heat_Call", "M0007", "B"),
            ("Unit_Model_ERROR", "M0017", "B"),
            ("OPSS_Config", "M0036", "B"),
            ("Standby_Valve_Pos", "M0082", "B"),
            ("Max_LWT_ACTIVE", "M0134", "B"),
            ("Comp_Start_Delay", "M0240", "B"),
            ("M0244_Unnamed", "M0244", "B"),
            ("Defrost", "M0350", "B"),
            ("Warning_Alarm_bit", "M0402", "B"),
            ("Lockout_Alarm_bit", "M0403", "B"),
            ("COLDTank_Probe_Fault", "M0427", "B"),
            ("HOT_Tank_Probe_Fault", "M0430", "B"),
            ("Cond_LWT_Probe_Fault", "M0431", "B"),
            ("Cond_EWT_Probe_Fault", "M0432", "B"),
            ("Amb_Air_Probe_Fault", "M0434", "B"),
            ("Master_Comm_Status", "M0950", "B"),
            ("Memeber_Unit_Status", "M0951", "B"),
            ("Password_Lock", "M1080", "B"),
            ("Service_Lock", "M1082", "B"),
            ("RTP_Config", "M1702", "B"),
            ("C90A_UnitModel", "M2000", "B"),
            ("C185A_UnitModel", "M2001", "B"),
            ("C250A_UnitModel", "M2002", "B"),
            ("e360A_UnitModel", "M2006", "B"),
            ("HPB_UnitModel", "M2007", "B"),
            ("e180_UnitModel", "M2010", "B"),
            ("O.P.S.S.", "M2035", "B"),
            ("Circ_Pump_Output", "M2051", "B"),
            ("Evap_Flow_Output", "M2053", "B"),
            ("Comp_Output", "M2056", "B"),
            ("HGBV_Output", "M2062", "B"),
            ("Ctrl_HB_MCPLA", "M7011", "B"),
            ("mqtt_member_status", "M7020", "B"),
        ],
    }
]

# HMI-originated commands. These need a write/command path rather than the
# ordinary source-to-HMI mirroring loop.
HMI_WRITE_COMMANDS = [
    ("Start_Cycle", "M0000", "B"),
    ("Stop_Cycle", "M0001", "B"),
                # Home screen data values.
            ("Tank_Probe_Fahr_F", "D0054", "F"),
            ("Cond_LWT_Fahr_F", "D0056", "F"),
            ("Cond_EWT_Fahr_F", "D0058", "F"),
            ("AMB_Fahr_F", "D0062", "F"),
            ("UNUSED_Fahr_F", "D0068", "F"),
            ("Cond_LWT_Setpoint_F", "D0280", "F"),
            ("Heatcall_status", "D1300", "W"),
            ("HGBV_OPSS", "D1301", "W"),
            ("AMB_EvapEWT", "D1302", "W"),
            ("Tank_Target_HMI_F", "D1320", "F"),
            ("Demand_Mode_Display", "D1350", "W"),
            ("Cond_Flow_F", "D3826", "F"),

            # HMI alarm-log source words.
            ("Alarm_Register_1", "D3500", "W"),
            ("Alarm_Register_2", "D3501", "W"),
            ("Alarm_Register_3", "D3502", "W"),

            # Home-screen state and visibility conditions.
            ("Cycle_Status", "M0002", "B"),
            ("AS_WS_Config", "M0003", "B"),
            ("HGBV_Config", "M0004", "B"),
            ("SinglePass_Config", "M0005", "B"),
            ("Demand_Mode", "M0006", "B"),
            ("Heat_Call", "M0007", "B"),
            ("Unit_Model_ERROR", "M0017", "B"),
            ("OPSS_Config", "M0036", "B"),
            ("Standby_Valve_Pos", "M0082", "B"),
            ("Max_LWT_ACTIVE", "M0134", "B"),
            ("Comp_Start_Delay", "M0240", "B"),
            ("M0244_Unnamed", "M0244", "B"),
            ("Defrost", "M0350", "B"),
            ("Warning_Alarm_bit", "M0402", "B"),
            ("Lockout_Alarm_bit", "M0403", "B"),
            ("COLDTank_Probe_Fault", "M0427", "B"),
            ("HOT_Tank_Probe_Fault", "M0430", "B"),
            ("Cond_LWT_Probe_Fault", "M0431", "B"),
            ("Cond_EWT_Probe_Fault", "M0432", "B"),
            ("Amb_Air_Probe_Fault", "M0434", "B"),
            ("Master_Comm_Status", "M0950", "B"),
            ("Memeber_Unit_Status", "M0951", "B"),
            ("Password_Lock", "M1080", "B"),
            ("Service_Lock", "M1082", "B"),
            ("RTP_Config", "M1702", "B"),
            ("C90A_UnitModel", "M2000", "B"),
            ("C185A_UnitModel", "M2001", "B"),
            ("C250A_UnitModel", "M2002", "B"),
            ("e360A_UnitModel", "M2006", "B"),
            ("HPB_UnitModel", "M2007", "B"),
            ("e180_UnitModel", "M2010", "B"),
            ("O.P.S.S.", "M2035", "B"),
            ("Circ_Pump_Output", "M2051", "B"),
            ("Evap_Flow_Output", "M2053", "B"),
            ("Comp_Output", "M2056", "B"),
            ("HGBV_Output", "M2062", "B"),
            ("Ctrl_HB_MCPLA", "M7011", "B"),
            ("mqtt_member_status", "M7020", "B"),
            ("Day_pass", "D3913","W"),
]

# Base Screen 1 also reads timer current values. The present B/F/W PLC_CONFIGS
# format and the older MiSmTCP implementation do not represent TC operands.
HMI_TIMER_CURRENT_VALUES = [
    ("TC_Comp_Off_Delay", 0),
    ("Pump_Delay_timer_TC", 22),
    ("MemStat_Timeout", 30),
    ("MQTT_Timeout", 38),
]

# Useful metadata, but not directly required by Base Screen 1.
OPTIONAL_META_REGISTERS = [
    ("Unit_Model", "D0102", "W"),
]

# Referenced elsewhere in the HMI project. These exceed the normal 4-digit
# MiSmTCP operand path and should remain separate until RA/extended addressing
# is implemented.
EXTENDED_REGISTERS = [
    ("Dev_Mode", "M10100", "B"),
    ("Connection_Error_Log", "D10392", "W"),
    ("Unit_number", "D10399", "W"),
    ("Master_IP_Octet_1", "D10400", "W"),
    ("Master_IP_Octet_2", "D10401", "W"),
    ("Master_IP_Octet_3", "D10402", "W"),
    ("Master_IP_Octet_4", "D10403", "W"),
    ("ErrorLog_Entries", "D10500", "W"),
]
