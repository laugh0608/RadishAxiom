use super::*;
use crate::{
    query::{GeneratorIdentity, QueryProfile, check_query},
    solver::{
        OuterTermination, SolverError, SolverProfile, SolverRequest, SolverRequestInput,
        SolverResponse, SolverResponseInput, SolverStatus, SolverToolIdentity,
        check_solver_request, parse_solver_response,
    },
};

pub(super) struct Solved {
    pub request: SolverRequest,
    pub response: Option<SolverResponse>,
    pub reason: Option<&'static str>,
}

pub(super) fn rebuild(
    run: &Execution<'_>,
    entry: &source::Entry,
    batch: &source::Batch,
    materials: Materials<'_, '_, '_>,
    tools: &BTreeMap<&str, Tool<'_>>,
    context: BackendReviewContext<'_>,
) -> Result<Solved> {
    let Materials {
        subject,
        artifacts,
        limits: review_limits,
    } = materials;
    limits::solve(run)?;
    roles(
        &run.inputs,
        &[
            "canonical-ir",
            "layout",
            "obligation-set",
            "query",
            "request",
            "symbols",
        ],
    )?;
    let document = subject
        .document
        .as_ref()
        .ok_or(invalid("backend", "missing IR"))?;
    let p2 = subject
        .p2
        .as_ref()
        .ok_or(invalid("backend", "missing P2"))?;
    if run.inputs["canonical-ir"] != subject.artifact
        || artifacts.get(
            run.inputs["obligation-set"],
            Some(("axiom-obligation-set", "0.2")),
        )? != p2.canonical_bytes()
    {
        return Err(invalid("backend", "IR or complete P2 binding"));
    }
    let request_raw = artifacts.get(
        run.inputs["request"],
        Some(("axiom-p4-solver-request", "0.2")),
    )?;
    let request_value = strict(request_raw, review_limits.evidence_json, "backend request")?;
    let budgets = limits::solver(
        named(named(&request_value, "limits")?, "component")?,
        context.solver_limits,
    )?;
    let generator_pin = string(
        named(named(&request_value, "binding")?, "generator_source")?,
        "generator",
    )?;
    artifacts.get(generator_pin, Some(("generator-source", "0.1")))?;
    let generator = GeneratorIdentity::new(generator_pin).map_err(ReviewError::Query)?;
    let query_info = named(&request_value, "query")?;
    artifacts.get(
        string(named(query_info, "query_rules")?, "query rule")?,
        Some(("evidence-rule", "0.1")),
    )?;
    artifacts.get(
        string(
            named(
                named(&request_value, "adapter")?,
                "base_execution_profile_digest",
            )?,
            "execution profile",
        )?,
        Some(("execution-profile", "0.1")),
    )?;
    let tool_value = named(&request_value, "tool")?;
    let tool = SolverToolIdentity::new(
        string(named(tool_value, "platform")?, "platform")?,
        string(named(tool_value, "payload_digest")?, "archive")?,
        string(named(tool_value, "acceptance_record_digest")?, "acceptance")?,
    )
    .map_err(ReviewError::Solver)?;
    let query = check_query(
        QueryProfile::MapFilterV0_5,
        artifacts.get(
            run.inputs["query"],
            Some(("axiom-smtlib2-qf-uflia-query0.3", "0.3")),
        )?,
        document,
        p2,
        run.target,
        &generator,
        budgets.base.query.with_compact(
            budgets
                .compact
                .ok_or(invalid("backend", "compact budgets"))?,
        ),
    )
    .map_err(ReviewError::Query)?;
    let request = check_solver_request(
        request_raw,
        SolverProfile::Cvc5Query0_3ModelV0_1,
        SolverRequestInput {
            document,
            obligations: p2,
            obligation_id: run.target,
            query_profile: QueryProfile::MapFilterV0_5,
            query: &query,
            generator: &generator,
            tool: &tool,
        },
        budgets,
    )
    .map_err(ReviewError::Solver)?;
    if artifacts.get(
        run.inputs["symbols"],
        Some(("axiom-p4-query-symbols", "0.1")),
    )? != request.symbol_bytes()
        || artifacts.get(run.inputs["layout"], Some(("axiom-p4-input-layout", "0.1")))?
            != request.layout_bytes()
    {
        return Err(invalid("backend", "symbols or layout binding"));
    }
    let capture = source::capture(
        run,
        entry,
        batch,
        artifacts,
        &tools[run.tool],
        &request,
        review_limits,
    )?;
    let (response, code) = if let Some(code) = capture.interruption {
        (None, Some(code))
    } else {
        match parse_solver_response(
            &request,
            SolverResponseInput {
                request_digest: request.artifact_digest(),
                stdout: capture.stdout,
                stderr: capture.stderr,
                stdout_complete: capture.stdout_complete,
                stderr_complete: capture.stderr_complete,
                exit: capture.exit,
                outer_termination: OuterTermination::None,
            },
        ) {
            Ok(response) => (Some(response), None),
            Err(SolverError::ResourceLimit { .. }) => (None, Some("component-limit")),
            Err(_) => (None, Some("protocol")),
        }
    };
    let terminal = if let Some(code) = code {
        roles(&run.outputs, &[])?;
        value_object([
            ("kind", value_string("interrupted")),
            ("code", value_string(code)),
        ])
    } else {
        roles(&run.outputs, &["response"])?;
        let response = response
            .as_ref()
            .ok_or(invalid("backend", "response missing"))?;
        if artifacts.get(
            run.outputs["response"],
            Some(("axiom-p4-solver-response-observation", "0.1")),
        )? != response.canonical_bytes()
        {
            return Err(invalid("backend", "response rebuild"));
        }
        let status = match response.status() {
            SolverStatus::Sat => "sat",
            SolverStatus::Unsat => "unsat",
            SolverStatus::Unknown => "unknown",
        };
        value_object([
            ("kind", value_string("completed")),
            ("status", value_string(status)),
        ])
    };
    if capture.terminal != encode(&terminal) {
        return Err(invalid("backend source", "capture terminal"));
    }
    execution_terminal(run, code)?;
    Ok(Solved {
        request,
        response,
        reason: code
            .map(|code| interrupted_reason(Mode::Solve, code))
            .transpose()?,
    })
}

pub(super) fn roles(references: &BTreeMap<&str, &str>, expected: &[&str]) -> Result<()> {
    if !references.keys().copied().eq(expected.iter().copied()) {
        return Err(invalid("backend", "input or output roles"));
    }
    Ok(())
}
