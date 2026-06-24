// ── Operator Learning Assistant — Wave 1 Seed Data ───────────────────────────
// Source: MANUAL (stable domain data from manuals + equipment records).
// All statements use MERGE — safe to re-run; will not create duplicates.

// ── Modalities ────────────────────────────────────────────────────────────────

MERGE (:Modality {name: 'VISUAL'});
MERGE (:Modality {name: 'TEXT'});
MERGE (:Modality {name: 'VIDEO'});

// ── Machine types ─────────────────────────────────────────────────────────────

MERGE (:MachineType {name: 'DieAttach'});
MERGE (:MachineType {name: 'WireBond'});
MERGE (:MachineType {name: 'FlipChip'});

// ── Machines (5 per type) ─────────────────────────────────────────────────────

// DieAttach
MERGE (m:Machine {id: 'DA-L1-01'}) SET m += {line: 'Line 1', install_date: '2021-03-15'};
MERGE (m:Machine {id: 'DA-L2-01'}) SET m += {line: 'Line 2', install_date: '2021-06-01'};
MERGE (m:Machine {id: 'DA-L2-02'}) SET m += {line: 'Line 2', install_date: '2022-01-10'};
MERGE (m:Machine {id: 'DA-L3-01'}) SET m += {line: 'Line 3', install_date: '2020-11-20'};
MERGE (m:Machine {id: 'DA-U4-01'}) SET m += {line: 'Unit 4', install_date: '2023-02-28'};

// WireBond
MERGE (m:Machine {id: 'WB-PA-01'}) SET m += {line: 'Press A', install_date: '2020-05-10'};
MERGE (m:Machine {id: 'WB-PB-01'}) SET m += {line: 'Press B', install_date: '2021-08-14'};
MERGE (m:Machine {id: 'WB-PC-01'}) SET m += {line: 'Press C', install_date: '2022-03-01'};
MERGE (m:Machine {id: 'WB-PD-01'}) SET m += {line: 'Press D', install_date: '2019-12-05'};
MERGE (m:Machine {id: 'WB-PE-01'}) SET m += {line: 'Press E', install_date: '2023-07-19'};

// FlipChip
MERGE (m:Machine {id: 'FC-L1-01'}) SET m += {line: 'Line 1', install_date: '2022-09-01'};
MERGE (m:Machine {id: 'FC-L1-02'}) SET m += {line: 'Line 1', install_date: '2023-01-15'};
MERGE (m:Machine {id: 'FC-L2-01'}) SET m += {line: 'Line 2', install_date: '2021-04-20'};
MERGE (m:Machine {id: 'FC-L3-01'}) SET m += {line: 'Line 3', install_date: '2020-07-30'};
MERGE (m:Machine {id: 'FC-L3-02'}) SET m += {line: 'Line 3', install_date: '2022-11-11'};

// ── Machine → MachineType ─────────────────────────────────────────────────────

MATCH (m:Machine) WHERE m.id STARTS WITH 'DA-'
MATCH (t:MachineType {name: 'DieAttach'})
MERGE (m)-[:OF_TYPE]->(t);

MATCH (m:Machine) WHERE m.id STARTS WITH 'WB-'
MATCH (t:MachineType {name: 'WireBond'})
MERGE (m)-[:OF_TYPE]->(t);

MATCH (m:Machine) WHERE m.id STARTS WITH 'FC-'
MATCH (t:MachineType {name: 'FlipChip'})
MERGE (m)-[:OF_TYPE]->(t);

// ── Skills ────────────────────────────────────────────────────────────────────

MERGE (:Skill {name: 'basic_alarm_response'});
MERGE (:Skill {name: 'pressure_system_maintenance'});
MERGE (:Skill {name: 'hydraulics'});
MERGE (:Skill {name: 'flow_calibration'});
MERGE (:Skill {name: 'sensor_diagnostics'});
MERGE (:Skill {name: 'recipe_management'});
MERGE (:Skill {name: 'wire_bond_setup'});
MERGE (:Skill {name: 'flip_chip_alignment'});

// ── Alarm codes ───────────────────────────────────────────────────────────────

MERGE (a:AlarmCode {code: 'PA-2201'})
SET a += {
  severity: 'medium',
  complexity: 'low',
  category: 'mechanical',
  expected_disposition: 'self_resolve'
};

MERGE (a:AlarmCode {code: 'PA-2202'})
SET a += {
  severity: 'high',
  complexity: 'medium',
  category: 'mechanical',
  expected_disposition: 'either'
};

MERGE (a:AlarmCode {code: 'HY-0042'})
SET a += {
  severity: 'high',
  complexity: 'high',
  category: 'mechanical',
  expected_disposition: 'escalate'
};

MERGE (a:AlarmCode {code: 'HY-0043'})
SET a += {
  severity: 'medium',
  complexity: 'high',
  category: 'mechanical',
  expected_disposition: 'escalate'
};

MERGE (a:AlarmCode {code: 'FL-1105'})
SET a += {
  severity: 'medium',
  complexity: 'medium',
  category: 'sensor',
  expected_disposition: 'either'
};

MERGE (a:AlarmCode {code: 'FL-1106'})
SET a += {
  severity: 'low',
  complexity: 'low',
  category: 'sensor',
  expected_disposition: 'self_resolve'
};

MERGE (a:AlarmCode {code: 'RC-3301'})
SET a += {
  severity: 'low',
  complexity: 'medium',
  category: 'recipe',
  expected_disposition: 'self_resolve'
};

MERGE (a:AlarmCode {code: 'SN-0710'})
SET a += {
  severity: 'medium',
  complexity: 'medium',
  category: 'sensor',
  expected_disposition: 'either'
};

// ── AlarmCode → MachineType (OCCURS_ON_TYPE) ──────────────────────────────────

MATCH (a:AlarmCode {code: 'PA-2201'}), (t:MachineType {name: 'DieAttach'})   MERGE (a)-[:OCCURS_ON_TYPE]->(t);
MATCH (a:AlarmCode {code: 'PA-2202'}), (t:MachineType {name: 'DieAttach'})   MERGE (a)-[:OCCURS_ON_TYPE]->(t);
MATCH (a:AlarmCode {code: 'HY-0042'}), (t:MachineType {name: 'WireBond'})    MERGE (a)-[:OCCURS_ON_TYPE]->(t);
MATCH (a:AlarmCode {code: 'HY-0043'}), (t:MachineType {name: 'WireBond'})    MERGE (a)-[:OCCURS_ON_TYPE]->(t);
MATCH (a:AlarmCode {code: 'FL-1105'}), (t:MachineType {name: 'DieAttach'})   MERGE (a)-[:OCCURS_ON_TYPE]->(t);
MATCH (a:AlarmCode {code: 'FL-1106'}), (t:MachineType {name: 'DieAttach'})   MERGE (a)-[:OCCURS_ON_TYPE]->(t);
MATCH (a:AlarmCode {code: 'RC-3301'}), (t:MachineType {name: 'FlipChip'})    MERGE (a)-[:OCCURS_ON_TYPE]->(t);
MATCH (a:AlarmCode {code: 'SN-0710'}), (t:MachineType {name: 'FlipChip'})    MERGE (a)-[:OCCURS_ON_TYPE]->(t);

// ── AlarmCode sibling links (RELATED_TO) ─────────────────────────────────────
// Weak evidence transfer: confidence on one alarm is weak signal for siblings.

MATCH (a1:AlarmCode {code: 'PA-2201'}), (a2:AlarmCode {code: 'PA-2202'}) MERGE (a1)-[:RELATED_TO]->(a2);
MATCH (a1:AlarmCode {code: 'HY-0042'}), (a2:AlarmCode {code: 'HY-0043'}) MERGE (a1)-[:RELATED_TO]->(a2);
MATCH (a1:AlarmCode {code: 'FL-1105'}), (a2:AlarmCode {code: 'FL-1106'}) MERGE (a1)-[:RELATED_TO]->(a2);

// ── Procedures ────────────────────────────────────────────────────────────────

MERGE (p:Procedure {id: 'PROC-PA-2201-RESET'})
SET p += {title: 'High Pressure Alarm Reset — PA-2200 Series'};

MERGE (p:Procedure {id: 'PROC-HY-0042-INSPECT'})
SET p += {title: 'Hydraulic Fault Inspection and Escalation'};

MERGE (p:Procedure {id: 'PROC-FL-1105-CALIB'})
SET p += {title: 'Flow Sensor Calibration — FL-1100 Series'};

MERGE (p:Procedure {id: 'PROC-RC-3301-RELOAD'})
SET p += {title: 'Recipe Parameter Reload'};

// ── ProcedureSteps ────────────────────────────────────────────────────────────

MERGE (s:ProcedureStep {id: 'PROC-PA-2201-RESET-S1'})
SET s += {order: 1, text: 'Check pressure gauge on Line 2 display panel.'};
MERGE (s:ProcedureStep {id: 'PROC-PA-2201-RESET-S2'})
SET s += {order: 2, text: 'If gauge reads >120 PSI, vent via manual relief valve V-4.'};
MERGE (s:ProcedureStep {id: 'PROC-PA-2201-RESET-S3'})
SET s += {order: 3, text: 'Wait 30 seconds, then reset alarm from HMI panel.'};
MERGE (s:ProcedureStep {id: 'PROC-PA-2201-RESET-S4'})
SET s += {order: 4, text: 'If alarm recurs within 10 minutes, escalate to maintenance.'};

MERGE (s:ProcedureStep {id: 'PROC-HY-0042-INSPECT-S1'})
SET s += {order: 1, text: 'Do not attempt reset. Isolate press hydraulics immediately.'};
MERGE (s:ProcedureStep {id: 'PROC-HY-0042-INSPECT-S2'})
SET s += {order: 2, text: 'Check hydraulic fluid level in reservoir sight glass.'};
MERGE (s:ProcedureStep {id: 'PROC-HY-0042-INSPECT-S3'})
SET s += {order: 3, text: 'Call maintenance supervisor — this fault requires specialist sign-off.'};

MERGE (s:ProcedureStep {id: 'PROC-FL-1105-CALIB-S1'})
SET s += {order: 1, text: 'Navigate to Unit 4 sensor diagnostics screen.'};
MERGE (s:ProcedureStep {id: 'PROC-FL-1105-CALIB-S2'})
SET s += {order: 2, text: 'Run auto-calibration sequence (takes ~2 min).'};
MERGE (s:ProcedureStep {id: 'PROC-FL-1105-CALIB-S3'})
SET s += {order: 3, text: 'Verify flow reading returns to nominal (4.5–5.5 L/min).'};
MERGE (s:ProcedureStep {id: 'PROC-FL-1105-CALIB-S4'})
SET s += {order: 4, text: 'Log calibration event in shift report.'};

// ── Procedure → ProcedureStep ─────────────────────────────────────────────────

MATCH (p:Procedure {id: 'PROC-PA-2201-RESET'}), (s:ProcedureStep) WHERE s.id STARTS WITH 'PROC-PA-2201-RESET-S'
MERGE (p)-[:HAS_STEP]->(s);

MATCH (p:Procedure {id: 'PROC-HY-0042-INSPECT'}), (s:ProcedureStep) WHERE s.id STARTS WITH 'PROC-HY-0042-INSPECT-S'
MERGE (p)-[:HAS_STEP]->(s);

MATCH (p:Procedure {id: 'PROC-FL-1105-CALIB'}), (s:ProcedureStep) WHERE s.id STARTS WITH 'PROC-FL-1105-CALIB-S'
MERGE (p)-[:HAS_STEP]->(s);

// ── AlarmCode → Procedure (RESOLVED_BY) ──────────────────────────────────────

MATCH (a:AlarmCode {code: 'PA-2201'}), (p:Procedure {id: 'PROC-PA-2201-RESET'})    MERGE (a)-[:RESOLVED_BY]->(p);
MATCH (a:AlarmCode {code: 'PA-2202'}), (p:Procedure {id: 'PROC-PA-2201-RESET'})    MERGE (a)-[:RESOLVED_BY]->(p);
MATCH (a:AlarmCode {code: 'HY-0042'}), (p:Procedure {id: 'PROC-HY-0042-INSPECT'})  MERGE (a)-[:RESOLVED_BY]->(p);
MATCH (a:AlarmCode {code: 'HY-0043'}), (p:Procedure {id: 'PROC-HY-0042-INSPECT'})  MERGE (a)-[:RESOLVED_BY]->(p);
MATCH (a:AlarmCode {code: 'FL-1105'}), (p:Procedure {id: 'PROC-FL-1105-CALIB'})    MERGE (a)-[:RESOLVED_BY]->(p);
MATCH (a:AlarmCode {code: 'FL-1106'}), (p:Procedure {id: 'PROC-FL-1105-CALIB'})    MERGE (a)-[:RESOLVED_BY]->(p);
MATCH (a:AlarmCode {code: 'RC-3301'}), (p:Procedure {id: 'PROC-RC-3301-RELOAD'})   MERGE (a)-[:RESOLVED_BY]->(p);

// ── Procedure → Skill (REQUIRES_SKILL) ───────────────────────────────────────

MATCH (p:Procedure {id: 'PROC-PA-2201-RESET'}),   (s:Skill {name: 'basic_alarm_response'})        MERGE (p)-[:REQUIRES_SKILL]->(s);
MATCH (p:Procedure {id: 'PROC-PA-2201-RESET'}),   (s:Skill {name: 'pressure_system_maintenance'}) MERGE (p)-[:REQUIRES_SKILL]->(s);
MATCH (p:Procedure {id: 'PROC-HY-0042-INSPECT'}), (s:Skill {name: 'hydraulics'})                  MERGE (p)-[:REQUIRES_SKILL]->(s);
MATCH (p:Procedure {id: 'PROC-FL-1105-CALIB'}),   (s:Skill {name: 'flow_calibration'})            MERGE (p)-[:REQUIRES_SKILL]->(s);
MATCH (p:Procedure {id: 'PROC-FL-1105-CALIB'}),   (s:Skill {name: 'sensor_diagnostics'})          MERGE (p)-[:REQUIRES_SKILL]->(s);
MATCH (p:Procedure {id: 'PROC-RC-3301-RELOAD'}),  (s:Skill {name: 'recipe_management'})           MERGE (p)-[:REQUIRES_SKILL]->(s);

// ── Procedure → Modality (AVAILABLE_IN) ──────────────────────────────────────

MATCH (p:Procedure {id: 'PROC-PA-2201-RESET'}),   (m:Modality {name: 'VISUAL'}) MERGE (p)-[:AVAILABLE_IN]->(m);
MATCH (p:Procedure {id: 'PROC-PA-2201-RESET'}),   (m:Modality {name: 'TEXT'})   MERGE (p)-[:AVAILABLE_IN]->(m);
MATCH (p:Procedure {id: 'PROC-HY-0042-INSPECT'}), (m:Modality {name: 'TEXT'})   MERGE (p)-[:AVAILABLE_IN]->(m);
MATCH (p:Procedure {id: 'PROC-FL-1105-CALIB'}),   (m:Modality {name: 'VISUAL'}) MERGE (p)-[:AVAILABLE_IN]->(m);
MATCH (p:Procedure {id: 'PROC-FL-1105-CALIB'}),   (m:Modality {name: 'VIDEO'})  MERGE (p)-[:AVAILABLE_IN]->(m);
MATCH (p:Procedure {id: 'PROC-RC-3301-RELOAD'}),  (m:Modality {name: 'TEXT'})   MERGE (p)-[:AVAILABLE_IN]->(m);

// ── Operators ─────────────────────────────────────────────────────────────────

MERGE (o:Operator {id: 'op-demo-01'})
SET o += {name: 'Max', tenure: 3, shift: 'day'};

MERGE (o:Operator {id: 'op-demo-02'})
SET o += {name: 'Reo',  tenure: 7, shift: 'night'};

MERGE (o:Operator {id: 'op-demo-03'})
SET o += {name: 'Tim', tenure: 1, shift: 'day'};

// ── Operator → Skill (CERTIFIED_FOR) ─────────────────────────────────────────

MATCH (o:Operator {id: 'op-demo-01'}), (s:Skill {name: 'basic_alarm_response'})        MERGE (o)-[:CERTIFIED_FOR]->(s);
MATCH (o:Operator {id: 'op-demo-01'}), (s:Skill {name: 'pressure_system_maintenance'}) MERGE (o)-[:CERTIFIED_FOR]->(s);
MATCH (o:Operator {id: 'op-demo-01'}), (s:Skill {name: 'flow_calibration'})            MERGE (o)-[:CERTIFIED_FOR]->(s);

MATCH (o:Operator {id: 'op-demo-02'}), (s:Skill {name: 'basic_alarm_response'})        MERGE (o)-[:CERTIFIED_FOR]->(s);
MATCH (o:Operator {id: 'op-demo-02'}), (s:Skill {name: 'hydraulics'})                  MERGE (o)-[:CERTIFIED_FOR]->(s);
MATCH (o:Operator {id: 'op-demo-02'}), (s:Skill {name: 'pressure_system_maintenance'}) MERGE (o)-[:CERTIFIED_FOR]->(s);
MATCH (o:Operator {id: 'op-demo-02'}), (s:Skill {name: 'sensor_diagnostics'})          MERGE (o)-[:CERTIFIED_FOR]->(s);

MATCH (o:Operator {id: 'op-demo-03'}), (s:Skill {name: 'basic_alarm_response'})        MERGE (o)-[:CERTIFIED_FOR]->(s);
