use super::*;
use crate::solver::ProcessExit;

pub(super) struct Entry {
    pub execution: String,
    pub invocation: String,
    pub request: String,
    pub upstream: Option<String>,
}

pub(super) struct Batch {
    pub policy: ProofPolicy,
    pub entries: Vec<Entry>,
}

impl Batch {
    pub fn read(
        context: BackendReviewContext<'_>,
        subject: &Subject<'_>,
        executions: &BTreeMap<&str, Execution<'_>>,
        limits: ReviewLimits,
    ) -> Result<Self> {
        if context.batch.len() > limits.evidence_json.max_input_bytes {
            return Err(ReviewError::Limit("backend batch bytes"));
        }
        if !digest(context.expected_batch_digest)
            || raw_digest(context.batch) != context.expected_batch_digest
        {
            return Err(invalid("backend source", "batch authority"));
        }
        let value = strict(context.batch, limits.evidence_json, "backend batch")?;
        let batch = shape(
            &value,
            "backend batch",
            &[
                "format",
                "version",
                "scope",
                "contract",
                "subject",
                "obligation_set",
                "proof_policy",
                "executions",
            ],
        )?;
        format(batch, "axiom-evidence-backend-batch")?;
        let document = subject
            .document
            .as_ref()
            .ok_or(invalid("backend source", "legal subject required"))?;
        let p2 = subject
            .p2
            .as_ref()
            .ok_or(invalid("backend source", "P2 required"))?;
        if text(batch, "scope")? != "simulation"
            || text(batch, "contract")? != raw_digest(CONTRACT)
            || text(batch, "subject")? != document.document_id()
            || text(batch, "obligation_set")? != p2.artifact_digest()
        {
            return Err(invalid("backend source", "batch scope or binding"));
        }
        let policy = ProofPolicy::read(text(batch, "proof_policy")?)?;
        let mut expected: Vec<_> = executions
            .iter()
            .filter(|(_, run)| run.mode.is_backend())
            .collect();
        expected.sort_by_key(|(_, run)| run.ordinal);
        let rows = items(batch, "executions")?;
        if rows.len() != expected.len() || rows.len() > limits.max_executions {
            return Err(invalid("backend source", "complete execution inventory"));
        }
        let mut invocations = BTreeSet::new();
        let mut entries: Vec<Entry> = Vec::new();
        for (row, (id, run)) in rows.iter().zip(expected) {
            let row = shape(
                row,
                "batch entry",
                &[
                    "execution",
                    "invocation",
                    "provenance",
                    "request",
                    "upstream",
                ],
            )?;
            let invocation = text(row, "invocation")?;
            let request = text(row, "request")?;
            if text(row, "execution")? != *id
                || text(row, "provenance")? != run.provenance
                || !digest(invocation)
                || !invocations.insert(invocation.to_owned())
                || run.inputs.get("request").copied() != Some(request)
            {
                return Err(invalid(
                    "backend source",
                    "entry binding or repeated invocation",
                ));
            }
            let upstream = member(row, "upstream");
            let upstream = match run.mode {
                Mode::Solve => {
                    let upstream = shape(upstream, "upstream", &["kind"])?;
                    if text(upstream, "kind")? != "none" {
                        return Err(invalid("backend source", "solve upstream"));
                    }
                    None
                }
                Mode::Replay => {
                    let upstream = shape(upstream, "upstream", &["kind", "execution"])?;
                    let parent = text(upstream, "execution")?;
                    if text(upstream, "kind")? != "solve"
                        || entries.last().is_none_or(|last| {
                            last.execution != parent
                                || last.upstream.is_some()
                                || last.request != request
                        })
                        || executions.get(parent).is_none_or(|solve| {
                            solve.mode != Mode::Solve || solve.target != run.target
                        })
                    {
                        return Err(invalid("backend source", "serial replay upstream"));
                    }
                    Some(parent.to_owned())
                }
                _ => return Err(invalid("backend source", "non-backend entry")),
            };
            entries.push(Entry {
                execution: (*id).to_owned(),
                invocation: invocation.to_owned(),
                request: request.to_owned(),
                upstream,
            });
        }
        Ok(Self { policy, entries })
    }
}

pub(super) struct Capture<'a> {
    pub stdout: &'a [u8],
    pub stderr: &'a [u8],
    pub exit: ProcessExit,
    pub stdout_complete: bool,
    pub stderr_complete: bool,
    pub interruption: Option<&'static str>,
    pub terminal: Vec<u8>,
}

pub(super) fn capture<'a>(
    run: &Execution<'_>,
    entry: &Entry,
    batch: &Batch,
    artifacts: &Artifacts<'_, 'a>,
    tool: &Tool<'_>,
    request: &crate::solver::SolverRequest,
    limits: ReviewLimits,
) -> Result<Capture<'a>> {
    let value = record(
        artifacts,
        run.provenance,
        "axiom-evidence-backend-capture",
        limits.evidence_json,
    )?;
    let envelope = shape(
        &value,
        "capture",
        &[
            "format",
            "version",
            "scope",
            "invocation",
            "launch",
            "observation",
            "proof_policy",
            "request",
            "stdout",
            "stderr",
            "terminal",
        ],
    )?;
    format(envelope, "axiom-evidence-backend-capture")?;
    if text(envelope, "scope")? != "simulation"
        || text(envelope, "invocation")? != entry.invocation
        || text(envelope, "request")? != entry.request
        || ProofPolicy::read(text(envelope, "proof_policy")?)? != batch.policy
    {
        return Err(invalid("backend source", "capture binding"));
    }
    let launch = shape(
        member(envelope, "launch"),
        "launch",
        &[
            "acceptance",
            "archive",
            "cli",
            "dependencies",
            "host",
            "policy",
            "qualification",
            "supervisor",
        ],
    )?;
    for (role, fmt) in [
        ("acceptance", "tool-acceptance"),
        ("archive", "tool-archive"),
        ("cli", "tool-executable"),
        ("dependencies", "tool-dependencies"),
        ("host", "host-qualification"),
        ("policy", "execution-policy"),
        ("qualification", "tool-qualification"),
        ("supervisor", "tool-executable"),
    ] {
        artifacts.get(text(launch, role)?, Some((fmt, "0.1")))?;
    }
    if text(launch, "archive")? != request.tool().payload_digest()
        || text(launch, "acceptance")? != request.tool().acceptance_record_digest()
        || text(launch, "cli")? != tool.artifact
        || text(launch, "cli")? == text(launch, "archive")?
    {
        return Err(invalid("backend source", "launch identity"));
    }
    let observed = record(
        artifacts,
        text(envelope, "observation")?,
        "axiom-evidence-capture-observation",
        limits.evidence_json,
    )?;
    let observation = shape(
        &observed,
        "capture observation",
        &[
            "format",
            "version",
            "scope",
            "invocation",
            "request",
            "source",
            "scheduled",
            "started",
            "stdin",
            "stdout",
            "stderr",
            "stdout_observed",
            "stderr_observed",
            "exit",
            "cleanup",
            "failures",
            "elapsed_ms",
        ],
    )?;
    format(observation, "axiom-evidence-capture-observation")?;
    if text(observation, "scope")? != "simulation"
        || text(observation, "invocation")? != entry.invocation
        || text(observation, "request")? != entry.request
        || !boolean(observation, "scheduled")?
        || encode(member(observation, "stdout")) != encode(member(envelope, "stdout"))
        || encode(member(observation, "stderr")) != encode(member(envelope, "stderr"))
    {
        return Err(invalid(
            "backend source",
            "observation binding or unscheduled",
        ));
    }
    artifacts.get(
        text(observation, "source")?,
        Some(("captured-source", "0.1")),
    )?;
    let started = boolean(observation, "started")?;
    let elapsed = decimal(text(observation, "elapsed_ms")?, "elapsed_ms")?;
    let out_count = decimal(text(observation, "stdout_observed")?, "stdout_observed")?;
    let err_count = decimal(text(observation, "stderr_observed")?, "stderr_observed")?;
    let stdout = stream(
        member(observation, "stdout"),
        artifacts,
        4_194_304,
        out_count,
    )?;
    let stderr = stream(member(observation, "stderr"), artifacts, 65_536, err_count)?;
    let stdin = member(observation, "stdin");
    let stdin_complete = match kind(stdin)? {
        "absent" => {
            shape(stdin, "stdin", &["kind"])?;
            false
        }
        "complete" | "prefix" => {
            let row = shape(stdin, "stdin", &["kind", "artifact"])?;
            let raw = artifacts.get(text(row, "artifact")?, None)?;
            if raw.len() > 1_048_576 || !request.stdin_bytes().starts_with(raw) {
                return Err(invalid("backend source", "actual stdin"));
            }
            let complete = text(row, "kind")? == "complete";
            if complete && raw != request.stdin_bytes() {
                return Err(invalid("backend source", "stdin completeness"));
            }
            complete
        }
        _ => return Err(invalid("backend source", "stdin kind")),
    };
    let exit = process_exit(member(observation, "exit"))?;
    let cleanup = text(observation, "cleanup")?;
    if !matches!(cleanup, "confirmed-empty" | "incomplete") {
        return Err(invalid("backend source", "cleanup kind"));
    }
    let mut primary = None;
    let mut seen = BTreeSet::new();
    let mut previous = None;
    for failure in items(observation, "failures")? {
        let failure = shape(failure, "failure", &["at_ms", "code"])?;
        let at = decimal(text(failure, "at_ms")?, "failure time")?;
        let code = failure_code(text(failure, "code")?)?;
        let rank = failure_rank(code);
        ordered(&mut previous, (at, rank), "failure ordering")?;
        if at > elapsed || (code == "deadline" && at < 6_000) {
            return Err(invalid("backend source", "failure time"));
        }
        if primary.is_none() {
            primary = Some(code);
        }
        seen.insert(code);
    }
    if (elapsed >= 6_000 && !seen.contains("deadline"))
        || (out_count > 4_194_304 && !seen.contains("stdout-limit"))
        || (err_count > 65_536 && !seen.contains("stderr-limit"))
        || (seen.contains("stdout-limit") && (out_count <= 4_194_304 || stdout.1))
        || (seen.contains("stderr-limit") && (err_count <= 65_536 || stderr.1))
        || (started && seen.contains("tool-unavailable"))
    {
        return Err(invalid("backend source", "resource or start facts"));
    }
    if !started
        && (primary != Some("tool-unavailable")
            || exit != ProcessExit::Unavailable
            || kind(stdin)? != "absent"
            || kind(member(observation, "stdout"))? != "absent"
            || kind(member(observation, "stderr"))? != "absent")
    {
        return Err(invalid("backend source", "unstarted attempt"));
    }
    let interruption = primary.or_else(|| {
        if exit != ProcessExit::Exited(0) {
            Some("exit")
        } else if cleanup != "confirmed-empty" {
            Some("cleanup")
        } else if !stdout.1 || !stderr.1 {
            Some("streams-incomplete")
        } else if !stdin_complete {
            Some("protocol")
        } else {
            None
        }
    });
    Ok(Capture {
        stdout: stdout.0,
        stderr: stderr.0,
        stdout_complete: stdout.1,
        stderr_complete: stderr.1,
        exit,
        interruption,
        terminal: encode(member(envelope, "terminal")),
    })
}

fn boolean(row: &Members, key: &str) -> Result<bool> {
    match member(row, key) {
        Value::Bool(value) => Ok(*value),
        _ => Err(invalid("backend source", "boolean")),
    }
}

fn stream<'a>(
    value: &Value,
    artifacts: &Artifacts<'_, 'a>,
    maximum: usize,
    observed: usize,
) -> Result<(&'a [u8], bool)> {
    match kind(value)? {
        "absent" => {
            shape(value, "stream", &["kind"])?;
            if observed != 0 {
                return Err(invalid("backend source", "absent stream length"));
            }
            Ok((&[], false))
        }
        "complete" | "prefix" => {
            let row = shape(value, "stream", &["kind", "artifact"])?;
            let bytes = artifacts.get(text(row, "artifact")?, Some(("raw-stream", "0.1")))?;
            let complete = text(row, "kind")? == "complete";
            if bytes.len() > maximum
                || observed < bytes.len()
                || (complete && observed != bytes.len())
                || (observed > maximum && bytes.len() != maximum)
            {
                return Err(invalid("backend source", "stream length"));
            }
            Ok((bytes, complete))
        }
        _ => Err(invalid("backend source", "stream kind")),
    }
}

fn process_exit(value: &Value) -> Result<ProcessExit> {
    let tag = kind(value)?;
    if tag == "unavailable" {
        shape(value, "exit", &["kind"])?;
        return Ok(ProcessExit::Unavailable);
    }
    let row = shape(value, "exit", &["kind", "code"])?;
    let code = u32::try_from(decimal(text(row, "code")?, "exit code")?)
        .map_err(|_| ReviewError::Limit("exit code"))?;
    match tag {
        "exited" => Ok(ProcessExit::Exited(code)),
        "signaled" => Ok(ProcessExit::Signaled(code)),
        _ => Err(invalid("backend source", "exit kind")),
    }
}

fn failure_code(code: &str) -> Result<&'static str> {
    match code {
        "deadline" => Ok("deadline"),
        "memory" => Ok("memory"),
        "stdout-limit" => Ok("stdout-limit"),
        "stderr-limit" => Ok("stderr-limit"),
        "exit" => Ok("exit"),
        "protocol" => Ok("protocol"),
        "cleanup" => Ok("cleanup"),
        "tool-unavailable" => Ok("tool-unavailable"),
        _ => Err(invalid("backend source", "failure code")),
    }
}

fn failure_rank(code: &str) -> usize {
    [
        "deadline",
        "memory",
        "stdout-limit",
        "stderr-limit",
        "exit",
        "protocol",
        "cleanup",
        "tool-unavailable",
    ]
    .iter()
    .position(|candidate| *candidate == code)
    .expect("validated failure code")
}
