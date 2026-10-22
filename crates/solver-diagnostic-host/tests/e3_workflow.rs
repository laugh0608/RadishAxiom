mod common;
#[path = "common/e3_workflow.rs"]
mod e3_workflow;
#[test]
fn original_capacity_crosses_wire_supervisor_and_p4b_only_as_simulation() {
    let exported = e3_workflow::full_workflow();
    assert_eq!(exported.query.len(), 962_642);
}

#[test]
fn causal_timing_matches_independent_unit_rate_matrix_without_qualification() {
    assert_eq!(e3_workflow::timing_matrix(), (891, 1809));
}
