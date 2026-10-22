use super::*;

#[test]
fn unknown_models_never_become_worlds_and_transport_failure_wins() {
    let req = request("minimal");
    for stdout in [b"unknown\n".as_slice(), b"unknown\n()\n".as_slice()] {
        let r = parse_solver_response(&req, response(&req, stdout)).unwrap();
        assert_eq!(r.status(), SolverStatus::Unknown);
        assert!(r.sat_model().is_none());
    }
    for stdout in [
        "unsat ()",
        "sat",
        "sat () sat",
        "unknown (error fail)",
        "sat (model)",
        "SAT",
        "unsat garbage",
        "sat (()",
    ] {
        assert!(
            parse_solver_response(&req, response(&req, stdout.as_bytes())).is_err(),
            "{stdout}"
        );
    }
    let mut input = response(&req, b"sat ()");
    input.exit = ProcessExit::Exited(1);
    input.outer_termination = OuterTermination::Deadline;
    input.stdout_complete = false;
    assert!(
        matches!(parse_solver_response(&req,input),Err(SolverError::Transport(v)) if v.outer_termination==OuterTermination::Deadline&&v.exit==ProcessExit::Exited(1)&&!v.stdout_complete)
    );
}

#[test]
fn complete_model_rejects_missing_duplicate_extra_names_and_all_wrong_grammars() {
    let req = request("identity");
    let source = synthetic(&req, false);
    let boolean = input_symbol(&req, 0, None);
    let integer = input_symbol(&req, 0, Some(0));
    let text = req
        .query
        .symbols()
        .iter()
        .find(|s| s.sort() == "Text")
        .unwrap()
        .name();
    for (name, values) in [
        (boolean.as_str(), vec!["0", "True", "(not true)", "|true|"]),
        (
            integer.as_str(),
            vec!["01", "+1", "-1", "(- 0)", "(/ 1 2)", "1.0", "(- 1 2)"],
        ),
        (
            text,
            vec![
                "\"é\"",
                "@Text_01",
                "(as @Text_0 Int)",
                "(let ((x @Text_0)) x)",
            ],
        ),
    ] {
        for value in values {
            let changed = replace_value(&req, &source, name, value);
            assert!(
                parse_solver_response(&req, response(&req, changed.as_bytes())).is_err(),
                "{name}: {value}"
            );
        }
    }
    let remove = |name: &str| {
        source
            .lines()
            .filter(|line| !line.starts_with(&format!("(define-fun {name} ")))
            .collect::<Vec<_>>()
            .join("\n")
    };
    for name in [&boolean, &integer, text] {
        let missing = remove(name);
        assert!(matches!(
            parse_solver_response(&req, response(&req, missing.as_bytes())),
            Err(SolverError::Model {
                reason: "missing-free-symbol",
                ..
            })
        ));
    }
    let line = source
        .lines()
        .find(|line| line.starts_with("(define-fun "))
        .unwrap();
    let duplicate = source.replacen(line, &format!("{line}\n{line}"), 1);
    assert!(parse_solver_response(&req, response(&req, duplicate.as_bytes())).is_err());
    let extra = source.replacen("\n)", "\n(define-fun arbitrary () Bool true)\n)", 1);
    assert!(parse_solver_response(&req, response(&req, extra.as_bytes())).is_err());
    let wrong = source.replacen(
        &format!("{boolean} () Bool"),
        &format!("{boolean} () Int"),
        1,
    );
    assert!(parse_solver_response(&req, response(&req, wrong.as_bytes())).is_err());
}

#[test]
fn typed_aliases_are_bounded_and_auxiliary_definitions_are_checked() {
    let req = request("identity");
    let source = synthetic(&req, false);
    let a = input_symbol(&req, 0, None);
    let c = input_symbol(&req, 1, None);
    let aliased = replace_value(&req, &source, &a, &c);
    let r = parse_solver_response(&req, response(&req, aliased.as_bytes())).unwrap();
    let original = parse_solver_response(&req, response(&req, source.as_bytes())).unwrap();
    assert_eq!(
        decode_model_world(&req, r.sat_model().unwrap())
            .unwrap()
            .world_bytes(),
        decode_model_world(&req, original.sat_model().unwrap())
            .unwrap()
            .world_bytes()
    );
    let cycle = replace_value(&req, &aliased, &c, &a);
    assert!(matches!(
        parse_solver_response(&req, response(&req, cycle.as_bytes())),
        Err(SolverError::Model {
            reason: "alias-cycle",
            reported_status: SolverStatus::Sat,
            ..
        })
    ));
    let unknown = cycle.replacen("sat", "unknown", 1);
    assert!(matches!(
        parse_solver_response(&req, response(&req, unknown.as_bytes())),
        Err(SolverError::Model {
            reason: "alias-cycle",
            reported_status: SolverStatus::Unknown,
            ..
        })
    ));
    let cross = input_symbol(&req, 0, Some(0));
    let source = replace_value(&req, &source, &a, &cross);
    assert!(parse_solver_response(&req, response(&req, source.as_bytes())).is_err());
    let auxiliary = req
        .catalogue
        .iter()
        .find(|(name, sort)| {
            **sort == Sort::Bool
                && !req
                    .query
                    .symbols()
                    .iter()
                    .any(|s| s.name() == name.as_str())
        })
        .unwrap()
        .0;
    let good = aliased.replacen(
        "\n)",
        &format!("\n(define-fun {auxiliary} () Bool true)\n)"),
        1,
    );
    let r = parse_solver_response(&req, response(&req, good.as_bytes())).unwrap();
    assert!(decode_model_world(&req, r.sat_model().unwrap()).is_ok());
    let bad = good.replacen(
        &format!("{auxiliary} () Bool true"),
        &format!("{auxiliary} () Bool (and true true)"),
        1,
    );
    assert!(parse_solver_response(&req, response(&req, bad.as_bytes())).is_err());
}

#[test]
fn inactive_and_none_payloads_do_not_bypass_protocol_but_skip_ir_range_checks() {
    let req = request("identity");
    let source = synthetic(&req, false);
    // 手算 identity 的叶顺序：fixed,flag,key,mode,nested.number,nested.optional-tag,bool,option-tag,int,text,x。
    let bad_enum = input_symbol(&req, 0, Some(3));
    let masked = replace_value(&req, &source, &bad_enum, "999");
    let r = parse_solver_response(&req, response(&req, masked.as_bytes())).unwrap();
    assert!(decode_model_world(&req, r.sat_model().unwrap()).is_ok());
    let active = replace_value(&req, &masked, &input_symbol(&req, 0, None), "true");
    let r = parse_solver_response(&req, response(&req, active.as_bytes())).unwrap();
    assert!(matches!(
        decode_model_world(&req, r.sat_model().unwrap()),
        Err(SolverError::InvalidInput {
            reason: "enum-index",
            ..
        })
    ));
    let source = replace_value(&req, &source, &input_symbol(&req, 0, None), "true");
    let hidden = replace_value(&req, &source, &input_symbol(&req, 0, Some(8)), "999");
    let r = parse_solver_response(&req, response(&req, hidden.as_bytes())).unwrap();
    assert!(decode_model_world(&req, r.sat_model().unwrap()).is_ok());
    let observed = replace_value(&req, &hidden, &input_symbol(&req, 0, Some(7)), "true");
    let r = parse_solver_response(&req, response(&req, observed.as_bytes())).unwrap();
    assert!(
        matches!(decode_model_world(&req,r.sat_model().unwrap()),Err(SolverError::InvalidInput{reason:"numeric-range",path,..}) if path==["option"])
    );
    let duplicate = synthetic(&req, true);
    let r = parse_solver_response(&req, response(&req, duplicate.as_bytes())).unwrap();
    assert!(matches!(
        decode_model_world(&req, r.sat_model().unwrap()),
        Err(SolverError::InvalidInput {
            reason: "duplicate-key",
            ..
        })
    ));
}

#[test]
fn text_literal_conflicts_and_atom_renaming_preserve_the_right_identities() {
    let req = request("unicode-literals");
    let source = synthetic(&req, false);
    let literal = req
        .query
        .symbols()
        .iter()
        .filter(|s| matches!(s.origin(), crate::query::SymbolOrigin::TextLiteral(_)))
        .collect::<Vec<_>>();
    assert!(literal.len() >= 3);
    let conflict = replace_value(&req, &source, literal[1].name(), "@Text_0");
    let r = parse_solver_response(&req, response(&req, conflict.as_bytes())).unwrap();
    assert!(matches!(
        decode_model_world(&req, r.sat_model().unwrap()),
        Err(SolverError::LiteralClassConflict)
    ));
    let req = request("identity");
    let source = replace_value(
        &req,
        &synthetic(&req, false),
        &input_symbol(&req, 0, None),
        "true",
    );
    let text = input_symbol(&req, 0, Some(9));
    let fresh = replace_value(&req, &source, &text, "@Text_999");
    let a = parse_solver_response(&req, response(&req, fresh.as_bytes())).unwrap();
    let a = decode_model_world(&req, a.sat_model().unwrap()).unwrap();
    let renamed = fresh.replace("@Text_999", "@Text_123");
    let c = parse_solver_response(&req, response(&req, renamed.as_bytes())).unwrap();
    let c = decode_model_world(&req, c.sat_model().unwrap()).unwrap();
    assert_eq!(a.world_bytes(), c.world_bytes());
    assert_eq!(a.text_class_bytes(), c.text_class_bytes());
    assert_ne!(a.artifact_digest(), c.artifact_digest());
    assert!(
        !std::str::from_utf8(a.text_class_bytes())
            .unwrap()
            .contains("@Text_")
    );
}

#[test]
fn binding_exit_stream_limits_and_utf8_never_default_to_success() {
    let req = request("minimal");
    let source = synthetic(&req, false);
    let mut input = response(&req, source.as_bytes());
    input.request_digest = "sha256:wrong";
    input.exit = ProcessExit::Exited(1);
    assert!(matches!(
        parse_solver_response(&req, input),
        Err(SolverError::BindingMismatch)
    ));
    for exit in [
        ProcessExit::Exited(1),
        ProcessExit::Signaled(9),
        ProcessExit::Unavailable,
    ] {
        let mut input = response(&req, source.as_bytes());
        input.exit = exit;
        assert!(matches!(
            parse_solver_response(&req, input),
            Err(SolverError::Transport(_))
        ));
    }
    for outer in [
        OuterTermination::Deadline,
        OuterTermination::Memory,
        OuterTermination::StdoutLimit,
        OuterTermination::StderrLimit,
        OuterTermination::Crash,
        OuterTermination::Unavailable,
    ] {
        let mut input = response(&req, source.as_bytes());
        input.outer_termination = outer;
        assert!(
            matches!(parse_solver_response(&req,input),Err(SolverError::Transport(v)) if v.outer_termination==outer)
        );
    }
    let mut input = response(&req, source.as_bytes());
    input.stderr_complete = false;
    assert!(matches!(
        parse_solver_response(&req, input),
        Err(SolverError::Transport(_))
    ));
    let large = vec![b'x'; 4_194_305];
    assert!(
        matches!(parse_solver_response(&req,response(&req,&large)),Err(SolverError::Transport(v)) if v.stdout_exceeded)
    );
    let large = vec![b'x'; 65537];
    let mut input = response(&req, source.as_bytes());
    input.stderr = &large;
    assert!(
        matches!(parse_solver_response(&req,input),Err(SolverError::Transport(v)) if v.stderr_exceeded)
    );
    for data in [b"\xff".as_slice(), b"unsat\x00".as_slice()] {
        assert!(matches!(
            parse_solver_response(&req, response(&req, data)),
            Err(SolverError::Protocol { .. })
        ));
    }
    let mut input = response(&req, b"unsat");
    input.stderr = b"sat timeout warning";
    assert_eq!(
        parse_solver_response(&req, input).unwrap().status(),
        SolverStatus::Unsat
    );
    let commented = "; ignored sat\r\n unsat ; garbage\n";
    assert_eq!(
        parse_solver_response(&req, response(&req, commented.as_bytes()))
            .unwrap()
            .status(),
        SolverStatus::Unsat
    );
}
