use super::*;

impl Bundle {
    pub(super) fn replay(
        &mut self,
        target: &str,
        solve: &str,
        request: &SolverRequest,
        response: &crate::solver::SolverResponse,
        host: String,
    ) -> Value {
        let ordinal = array_mut(field_mut(&mut self.document, "executions")).len();
        let invocation = raw_digest(format!("synthetic replay invocation {ordinal}").as_bytes());
        let actor = self.tool(
            "review-replayer",
            "counterexample-replayer",
            b"synthetic replay executable",
        );
        let rule = self.add(REPLAY_RULE.1, "evidence-rule", "0.1");
        let generator_pin = self.add(REPLAY_SOURCE, "generator-source", "0.1");
        let generator = GeneratorIdentity::new(&generator_pin).unwrap();
        let model = response.sat_model().unwrap();
        let mut inputs = vec![
            ("canonical-ir", raw_digest(self.ir.canonical_bytes())),
            ("obligation-set", self.p2.artifact_digest().to_owned()),
            ("request", request.artifact_digest().to_owned()),
            ("response", response.artifact_digest().to_owned()),
        ];
        let mut candidate = None;
        let mut observed = None;
        let mut failure = None;
        match decode_model_world(request, model) {
            Err(error) => {
                failure = Some((
                    "model",
                    if matches!(error, crate::solver::SolverError::ResourceLimit { .. }) {
                        "component-limit"
                    } else {
                        "model-decode"
                    },
                    format!("{error:?}"),
                ));
            }
            Ok(decoded) => {
                inputs.push((
                    "model-world-candidate",
                    self.add(
                        decoded.canonical_bytes(),
                        "axiom-p4-model-world-candidate",
                        "0.1",
                    ),
                ));
                inputs.push((
                    "world",
                    self.add(decoded.world_bytes(), "axiom-p4-world", "0.1"),
                ));
                match replay_target(
                    ReplayProfile::MapFilterV0_1,
                    ReplayInput {
                        document: &self.ir,
                        obligations: &self.p2,
                        obligation_id: target,
                        generator: &generator,
                        world: ReplayWorldInput::ModelCandidate {
                            request,
                            model,
                            candidate: &decoded,
                        },
                    },
                    self.replay_budget,
                ) {
                    Ok(value) => {
                        observed = Some(value);
                    }
                    Err(error) => {
                        let code = match error {
                            crate::replay::ReplayError::ResourceLimit { .. } => "component-limit",
                            crate::replay::ReplayError::UnsupportedProfile
                            | crate::replay::ReplayError::UnsupportedIrVersion(_)
                            | crate::replay::ReplayError::UnsupportedKind(_)
                            | crate::replay::ReplayError::UnsupportedFeature { .. } => {
                                "unsupported"
                            }
                            _ => "replay-error",
                        };
                        failure = Some(("replay", code, format!("{error:?}")));
                    }
                }
                candidate = Some(decoded);
            }
        }
        let (observation, terminal, state, outputs) = if let Some((stage, code, detail)) = &failure
        {
            let diagnostic = value_object([
                ("format", value_string("axiom-evidence-replay-interruption")),
                ("version", value_string("0.1")),
                ("scope", value_string("simulation")),
                ("request", value_string(request.artifact_digest())),
                ("solve_execution", value_string(solve)),
                ("generator", value_string(&generator_pin)),
                ("stage", value_string(stage)),
                ("code", value_string(code)),
                ("detail", value_string(detail)),
            ]);
            let pin = self.add(
                &encode(&diagnostic),
                "axiom-evidence-replay-interruption",
                "0.1",
            );
            let state = value_object([
                ("kind", value_string("interrupted")),
                ("code", value_string(code)),
            ]);
            (pin, copied(&state), state, vec![])
        } else {
            let observed = observed.as_ref().unwrap();
            let pin = self.add(
                observed.canonical_bytes(),
                "axiom-p4-target-replay-observation",
                "0.1",
            );
            let terminal = value_object([
                ("kind", value_string("completed")),
                (
                    "outcome",
                    value_string(match observed.outcome() {
                        crate::replay::ReplayOutcome::InputRejected => "input-rejected",
                        crate::replay::ReplayOutcome::PreRejected => "pre-rejected",
                        crate::replay::ReplayOutcome::TargetNotViolated => "target-not-violated",
                        crate::replay::ReplayOutcome::TargetViolated => "target-violated",
                    }),
                ),
            ]);
            (
                pin.clone(),
                terminal,
                value_object([("kind", value_string("completed"))]),
                vec![("target-replay", pin)],
            )
        };
        let source = value_object([
            (
                "format",
                value_string("axiom-evidence-backend-replay-source"),
            ),
            ("version", value_string("0.1")),
            ("scope", value_string("simulation")),
            ("invocation", value_string(&invocation)),
            ("observation", value_string(&observation)),
            ("solve_execution", value_string(solve)),
            ("terminal", terminal),
        ]);
        let provenance = self.add(
            &encode(&source),
            "axiom-evidence-backend-replay-source",
            "0.1",
        );
        let execution = self.execution(
            value_object([
                ("kind", value_string("replay-counterexample")),
                ("mode", value_string("p4-target-replay-v0.1")),
                ("tool", value_string(&actor)),
                ("rule", value_string(&rule)),
                ("provenance", value_string(&provenance)),
                ("ordinal", value_string(&ordinal.to_string())),
                ("obligation", value_string(target)),
                ("inputs", refs(&inputs)),
                ("outputs", refs(&outputs)),
                ("limits", replay_limit_rows(self.replay_budget)),
                ("result", state),
            ]),
            &invocation,
            request.artifact_digest(),
            Some(solve),
        );
        let replay_host = self.trust("host-runtime", "execution", &execution);
        if let Some((_, code, _)) = failure {
            return test_unknown(
                &execution,
                match code {
                    "component-limit" => "resource-exhausted",
                    "unsupported" => "unsupported",
                    _ => "operational-error",
                },
            );
        }
        let observed = observed.unwrap();
        if observed.outcome() != crate::replay::ReplayOutcome::TargetViolated {
            return test_unknown(&execution, "indeterminate");
        }
        let ir = strict(self.ir.canonical_bytes(), json_limits(), "IR").unwrap();
        let Value::Array(contracts) = get(&ir, "contracts") else {
            panic!("contracts")
        };
        let assumes = contracts
            .iter()
            .filter(|c| string(get(get(c, "definition"), "role"), "role").unwrap() == "assume")
            .map(|c| string(get(c, "id"), "id").unwrap().to_owned())
            .collect();
        let result = strict(observed.result_bytes(), json_limits(), "result").unwrap();
        value_object([
            ("kind", value_string("failed")),
            ("execution", value_string(&execution)),
            ("assumptions", test_strings(vec![host, replay_host])),
            (
                "counterexample",
                value_object([
                    ("kind", value_string("target-replay")),
                    (
                        "minimality",
                        value_object([("kind", value_string("unreduced"))]),
                    ),
                    ("observed", copied(get(&result, "witness"))),
                    ("preconditions", test_strings(assumes)),
                    (
                        "worlds",
                        Value::Array(vec![
                            strict(candidate.unwrap().world_bytes(), json_limits(), "world")
                                .unwrap(),
                        ]),
                    ),
                    (
                        "trace",
                        Value::Array(vec![
                            value_object([
                                ("kind", value_string("obligation")),
                                ("ref", value_string(target)),
                            ]),
                            value_object([
                                ("kind", value_string("replay-observation")),
                                ("artifact", value_string(&observation)),
                            ]),
                        ]),
                    ),
                ]),
            ),
        ])
    }

    pub fn finish(&mut self) {
        assert_eq!(
            self.results.len(),
            self.targets.len(),
            "fixture must execute every target"
        );
        let core_ids: BTreeSet<_> = array_mut(field_mut(&mut self.document, "obligations"))
            .iter()
            .map(|row| string(get(row, "id"), "id").unwrap().to_owned())
            .collect();
        for target in self.p2.obligations() {
            if core_ids.contains(target.id()) {
                continue;
            }
            let definition =
                strict(target.canonical_definition(), json_limits(), "definition").unwrap();
            array_mut(field_mut(&mut self.document, "obligations")).push(value_object([
                ("id", value_string(target.id())),
                ("definition", definition),
                ("result", copied(&self.results[target.id()])),
            ]));
        }
        let trusts: Vec<_> = array_mut(field_mut(&mut self.document, "trust"))
            .iter()
            .map(copied)
            .collect();
        for trust in trusts {
            let pin = string(get(&trust, "id"), "id").unwrap();
            let definition = value_object([
                ("kind", value_string("trust-boundary")),
                ("expectation", value_string("trust")),
                (
                    "subject",
                    value_object([
                        ("kind", value_string("trust")),
                        ("scope", value_string(pin)),
                        (
                            "category",
                            copied(get(get(&trust, "definition"), "category")),
                        ),
                    ]),
                ),
            ]);
            let obligation = value_object([
                (
                    "id",
                    value_string(&content_id(OBLIGATION_DOMAIN, &encode(&definition))),
                ),
                ("definition", definition),
                (
                    "result",
                    value_object([
                        ("kind", value_string("trusted")),
                        ("trust", value_string(pin)),
                    ]),
                ),
            ]);
            array_mut(field_mut(&mut self.document, "obligations")).push(obligation);
        }
        let mut failed = Vec::new();
        let mut unknown = Vec::new();
        for (target, result) in &self.results {
            match kind(result).unwrap() {
                "failed" => failed.push(target.clone()),
                "unknown" => unknown.push(target.clone()),
                _ => {}
            }
        }
        let (conclusion, refs) = if !failed.is_empty() {
            ("violated", failed)
        } else if !unknown.is_empty() {
            ("inconclusive", unknown)
        } else {
            ("satisfied", vec![])
        };
        *field_mut(&mut self.document, "conclusion") = value_object([
            ("kind", value_string(conclusion)),
            ("refs", test_strings(refs)),
        ]);
        for (field, key) in [
            ("artifacts", "content_digest"),
            ("tools", "id"),
            ("executions", "id"),
            ("obligations", "id"),
            ("trust", "id"),
        ] {
            array_mut(field_mut(&mut self.document, field)).sort_by(|a, b| {
                string(get(a, key), key)
                    .unwrap()
                    .cmp(string(get(b, key), key).unwrap())
            });
        }
        self.batch = value_object([
            ("format", value_string("axiom-evidence-backend-batch")),
            ("version", value_string("0.1")),
            ("scope", value_string("simulation")),
            ("contract", value_string(&raw_digest(CONTRACT))),
            ("subject", value_string(self.ir.document_id())),
            ("obligation_set", value_string(self.p2.artifact_digest())),
            ("proof_policy", value_string(self.production_policy)),
            (
                "executions",
                Value::Array(std::mem::take(&mut self.history)),
            ),
        ]);
    }
    pub fn verify(&self) -> Result<Readback> {
        self.verify_policy(ProofPolicy::AttestationAllowed, ALLOWED)
    }
    pub fn verify_policy(&self, policy: ProofPolicy, allowed: &[&str]) -> Result<Readback> {
        let batch = encode(&self.batch);
        readback_v02_with_backend(
            &encode(&self.document),
            |pin| self.blobs.get(pin).map(Vec::as_slice),
            review_limits(),
            BackendReviewContext {
                batch: &batch,
                expected_batch_digest: &raw_digest(&batch),
                consumer_policy: policy,
                allowed_trust_categories: allowed,
                solver_limits: solver_limits(),
                replay_limits: replay_limits(),
            },
        )
    }
}
