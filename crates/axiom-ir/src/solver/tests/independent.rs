use super::*;

fn check_independent(
    req: &SolverRequest,
    document: &CanonicalDocument,
    set: &ObligationSet,
    stdout: &str,
    hand: bool,
) {
    let response = parse_solver_response(req, super::response(req, stdout.as_bytes())).unwrap();
    let candidate = decode_model_world(req, response.sat_model().unwrap()).unwrap();
    let stamp = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap()
        .as_nanos();
    let dir = std::env::temp_dir().join(format!("radishaxiom-p4a-{}-{stamp}", std::process::id()));
    std::fs::create_dir(&dir).unwrap();
    for (name, bytes) in [
        ("ir.jcs", document.canonical_bytes()),
        ("p2.jcs", set.canonical_bytes()),
        ("query.smt2", req.stdin_bytes()),
        ("symbols.jcs", req.symbol_bytes()),
        ("layout.jcs", req.layout_bytes()),
        ("request.jcs", req.canonical_bytes()),
        ("stdout.smt2", stdout.as_bytes()),
        ("response.jcs", response.canonical_bytes()),
        ("candidate.jcs", candidate.canonical_bytes()),
    ] {
        std::fs::write(dir.join(name), bytes).unwrap();
    }
    if hand {
        std::fs::copy(
            root().join("contracts/solver-model-v0.1/hand-cases.json"),
            dir.join("hand-cases.json"),
        )
        .unwrap();
    }
    let result = std::process::Command::new("python3")
        .arg(root().join("scripts/check-p4a-model-world.py"))
        .arg(&dir)
        .output()
        .unwrap();
    assert!(
        result.status.success(),
        "{}; materials retained at {}",
        String::from_utf8_lossy(&result.stderr),
        dir.display()
    );
    std::fs::remove_dir_all(dir).unwrap();
}

#[test]
fn composite_sparse_model_matches_independent_layout_and_hand_values() {
    let l = limits();
    let (d, set, q) = setup("contracts/solver-model-v0.1/inputs/composite.jcs", l);
    let req = plan(&d, &set, &q, l).unwrap();
    // Fixture 使用 number/null，仅由已安装 Python 转为供测试读取的字符串模型。
    let result=std::process::Command::new("python3").arg("-c").arg(
        "import json,sys; d=json.load(open(sys.argv[1])); syms=json.load(sys.stdin)['symbols']; out=['sat','('];\nfor s in syms:\n o=s['origin']; v=d['literal_atoms'][o['value']] if o['kind']=='text-literal' else (str(d['slots'][o['interface']][int(o['slot'])]['active']).lower() if o['component']=='active' else d['slots'][o['interface']][int(o['slot'])]['values'][int(o['component'])]); out.append('(define-fun '+s['name']+' () '+s['sort']+' '+v+')')\nout.append(')'); print('\\n'.join(out))"
    ).arg(root().join("contracts/solver-model-v0.1/hand-cases.json")).stdin(std::process::Stdio::piped()).stdout(std::process::Stdio::piped()).spawn().and_then(|mut child|{use std::io::Write;child.stdin.take().unwrap().write_all(req.symbol_bytes())?;child.wait_with_output()}).unwrap();
    assert!(result.status.success());
    let stdout = String::from_utf8(result.stdout).unwrap();
    check_independent(&req, &d, &set, &stdout, true);
    let r = parse_solver_response(&req, response(&req, stdout.as_bytes())).unwrap();
    let first = decode_model_world(&req, r.sat_model().unwrap()).unwrap();
    let mut lines: Vec<_> = stdout
        .lines()
        .filter(|line| line.starts_with("(define-fun "))
        .collect();
    lines.reverse();
    let reordered = format!("sat\n(\n{}\n)\n", lines.join("\n"));
    let r = parse_solver_response(&req, response(&req, reordered.as_bytes())).unwrap();
    let second = decode_model_world(&req, r.sat_model().unwrap()).unwrap();
    assert_eq!(first.world_bytes(), second.world_bytes());
    assert_eq!(first.text_class_bytes(), second.text_class_bytes());
    assert_ne!(first.artifact_digest(), second.artifact_digest());
    check_independent(&req, &d, &set, &reordered, true);
}

#[test]
fn all_existing_synthetic_inputs_have_independently_reconstructed_empty_worlds() {
    let l = limits();
    let mut count = 0;
    for version in ["v0.1", "v0.2", "v0.3"] {
        let paths = root().join(format!("contracts/map-filter-query-{version}/inputs"));
        for path in std::fs::read_dir(paths).unwrap() {
            let path = path.unwrap().path();
            if path.extension().is_none_or(|v| v != "jcs") {
                continue;
            }
            let document =
                check_canonical_document(&std::fs::read(&path).unwrap(), l.query.ir_json).unwrap();
            let set = generate_obligations(
                &document,
                ObligationProfile::VerificationV0_2,
                ObligationLimits {
                    ir_json: l.query.ir_json,
                    max_obligations: 100000,
                    max_definition_bytes: 16000000,
                    max_path_bytes: 8000000,
                    max_output_bytes: 24000000,
                },
            )
            .unwrap();
            let Some(target) = set
                .obligations()
                .iter()
                .find(|o| o.kind() == ObligationKind::ContractGuarantee)
            else {
                continue;
            };
            let q = encode_query(
                QueryProfile::MapFilterV0_4,
                &document,
                &set,
                target.id(),
                &generator(),
                l.query,
            )
            .unwrap();
            let req = plan(&document, &set, &q, l).unwrap();
            check_independent(&req, &document, &set, &synthetic(&req, false), false);
            count += 1;
        }
    }
    assert!(count >= 50);
}

#[test]
fn request_rebuild_preserves_existing_query_bytes() {
    let l = limits();
    let (d, s, q) = setup("contracts/map-filter-query-v0.1/inputs/identity.jcs", l);
    let req = plan(&d, &s, &q, l).unwrap();
    assert_eq!(req.stdin_bytes(), q.bytes());
    assert_eq!(req.query.symbols(), q.symbols());
    assert_eq!(req.query.usage(), q.usage());
    let mut tampered = req.canonical_bytes().to_vec();
    tampered.push(b'\n');
    assert!(matches!(
        check_solver_request(
            &tampered,
            SolverProfile::Cvc5Query0_2ModelV0_1,
            SolverRequestInput {
                document: &d,
                obligations: &s,
                obligation_id: q.binding().obligation(),
                query_profile: QueryProfile::MapFilterV0_4,
                query: &q,
                generator: &generator(),
                tool: &tool()
            },
            l
        ),
        Err(SolverError::NonCanonical { .. })
    ));
}
