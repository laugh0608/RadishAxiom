use radishaxiom_solver_supervision_core::{bootstrap_start::*, handshake::*, wire::*};
const QUERY: &[u8] = b"abc";
fn window() -> HandshakeWindow {
    HandshakeWindow {
        wall_clock_ns: 6000,
    }
}
fn start() -> StartDescription {
    StartDescription::new(
        StartFields {
            attempt: [1; 32],
            request: [2; 32],
            query_bytes: 3,
            query_digest: radishaxiom_digest::digest(QUERY),
            policy_bundle: [3; 32],
            image: [4; 32],
            cli_acceptance: [5; 32],
            configuration: [6; 32],
        },
        WireLimits {
            query_bytes: 32,
            stdout_bytes: 64,
            stderr_bytes: 16,
        },
    )
    .unwrap()
}
fn local() -> LocalReadyDeclaration {
    LocalReadyDeclaration {
        boot_digest: [7; 32],
        namespace_digest: [8; 32],
        configuration_digest: [6; 32],
        nonce: [9; 32],
    }
}
fn m(t: u64) -> MacInstant {
    MacInstant::declared_ns(t)
}
fn l(t: u64) -> LinuxInstant {
    LinuxInstant::declared_ns(t)
}
fn mac(delta: u64) -> MacHandshake {
    MacHandshake::new(
        start(),
        m(100),
        delta,
        ExpectedReadyDeclaration {
            boot_digest: [7; 32],
            namespace_digest: [8; 32],
        },
        window(),
    )
    .unwrap()
}
fn supervisor() -> SupervisorHandshake {
    SupervisorHandshake::new(start(), l(1000), local(), window()).unwrap()
}
fn ready() -> BootstrapFrame {
    supervisor().ready(l(1100)).unwrap()
}
fn arm() -> BootstrapFrame {
    mac(10).receive_ready(m(300), &ready()).unwrap()
}
fn armed() -> SupervisorHandshake {
    let mut s = supervisor();
    s.ready(l(1100)).unwrap();
    s.receive_arm(l(1200), &arm()).unwrap();
    s
}
#[test]
fn separated_s_never_makes_arm_and_header_does_not_complete_query() {
    let mut s = supervisor();
    let mut mac = mac(10);
    let ready = s.ready(l(1100)).unwrap();
    let frame = mac.receive_ready(m(300), &ready).unwrap();
    let BootstrapMessage::Arm(a) = &frame.message else {
        panic!()
    };
    assert_eq!(a.deadline_ns, 6890);
    assert_eq!(mac.deadline(), m(6100));
    assert_eq!(s.preparation_deadline(), l(7000));
    let plan = s.receive_arm(l(1200), &frame).unwrap();
    assert_eq!(plan.deadline(), l(6890));
    assert_eq!(plan.scope(), "external-declaration-check-and-plan");
    let checked = s.query_complete(l(1300), &frame.binding, QUERY).unwrap();
    assert_eq!(checked.deadline(), l(6890));
    assert_eq!(checked.binding(), &frame.binding);
    assert_eq!(checked.scope(), mac.scope());
    assert_eq!(s.scope(), mac.scope());
    // Completion values are plans with no normal-response or authenticated-capture conversion.
    assert!(s.query_complete(l(1301), &frame.binding, QUERY).is_err());
}
#[test]
fn arm_is_received_without_s_access_to_mac_clock_or_local_offer() {
    let mut s = supervisor();
    s.ready(l(1100)).unwrap();
    let frame = BootstrapFrame {
        binding: start().binding(local().nonce),
        message: BootstrapMessage::Arm(Arm {
            deadline_ns: 1500,
            query_len: 3,
            query_digest: radishaxiom_digest::digest(QUERY),
        }),
    };
    assert_eq!(s.receive_arm(l(1200), &frame).unwrap().deadline(), l(1500));
    assert!(s.query_complete(l(1499), &frame.binding, QUERY).is_ok());
}
#[test]
fn every_binding_field_configuration_and_ready_identity_is_checked() {
    for index in 0..5 {
        let mut r = ready();
        match index {
            0 => r.binding.attempt[0] ^= 1,
            1 => r.binding.request[0] ^= 1,
            2 => r.binding.policy[0] ^= 1,
            3 => r.binding.image[0] ^= 1,
            _ => r.binding.nonce[0] ^= 1,
        }
        // Mac learns only a declared initial nonce; S rejects an incorrect echo.
        if index < 4 {
            let mut mac = mac(10);
            let error = mac.receive_ready(m(300), &r).unwrap_err();
            assert!(matches!(error, HandshakeError::Binding { .. }));
            assert_eq!(mac.tick(m(301)), Err(error));
        }
        let mut a = arm();
        match index {
            0 => a.binding.attempt[0] ^= 1,
            1 => a.binding.request[0] ^= 1,
            2 => a.binding.policy[0] ^= 1,
            3 => a.binding.image[0] ^= 1,
            _ => a.binding.nonce[0] ^= 1,
        }
        let mut s = supervisor();
        s.ready(l(1100)).unwrap();
        let error = s.receive_arm(l(1200), &a).unwrap_err();
        assert!(matches!(error, HandshakeError::Binding { .. }));
        assert_eq!(s.tick(l(1201)), Err(error));
    }
    for index in 0..3 {
        let mut r = ready();
        let BootstrapMessage::Ready(v) = &mut r.message else {
            panic!()
        };
        match index {
            0 => v.configuration_digest[0] ^= 1,
            1 => v.boot_digest[0] ^= 1,
            _ => v.namespace_digest[0] ^= 1,
        }
        assert!(matches!(
            mac(10).receive_ready(m(300), &r),
            Err(HandshakeError::Binding { .. })
        ));
    }
    let mut declaration = local();
    declaration.configuration_digest[0] ^= 1;
    assert!(matches!(
        SupervisorHandshake::new(start(), l(1000), declaration, window()),
        Err(HandshakeError::Binding {
            field: "configuration"
        })
    ));
}
#[test]
fn replay_wrong_message_wrong_query_and_missing_arm_poison() {
    let mut mac_state = mac(10);
    mac_state.receive_ready(m(300), &ready()).unwrap();
    let error = mac_state.receive_ready(m(301), &ready()).unwrap_err();
    assert_eq!(mac_state.tick(m(302)), Err(error));
    let mut s = supervisor();
    s.ready(l(1100)).unwrap();
    let error = s.ready(l(1101)).unwrap_err();
    assert_eq!(s.tick(l(1102)), Err(error));
    let mut s = armed();
    let error = s.receive_arm(l(1300), &arm()).unwrap_err();
    assert_eq!(s.tick(l(1301)), Err(error));
    assert!(supervisor().receive_arm(l(1100), &arm()).is_err());
    assert!(mac(10).receive_ready(m(300), &arm()).is_err());
    let mut s = supervisor();
    s.ready(l(1100)).unwrap();
    assert!(s.receive_arm(l(1200), &ready()).is_err());
    for index in 0..2 {
        let mut a = arm();
        let BootstrapMessage::Arm(v) = &mut a.message else {
            panic!()
        };
        if index == 0 {
            v.query_len += 1
        } else {
            v.query_digest[0] ^= 1
        }
        let mut s = supervisor();
        s.ready(l(1100)).unwrap();
        assert!(matches!(
            s.receive_arm(l(1200), &a),
            Err(HandshakeError::Query { .. })
        ));
    }
    for bytes in [&b"ab"[..], &b"abd"[..]] {
        let mut s = armed();
        let error = s
            .query_complete(l(1300), &arm().binding, bytes)
            .unwrap_err();
        assert_eq!(s.tick(l(1301)), Err(error));
    }
    let mut s = supervisor();
    s.ready(l(1100)).unwrap();
    assert!(s.query_complete(l(1200), &arm().binding, QUERY).is_err());
    let mut s = armed();
    let mut b = arm().binding;
    b.nonce[0] ^= 1;
    assert!(matches!(
        s.query_complete(l(1300), &b, QUERY),
        Err(HandshakeError::Binding { field: "nonce" })
    ));
}
#[test]
fn timing_matrix_has_no_clamp_extension_or_cross_clock_subtraction() {
    for delta in [0, 10, 5799] {
        let mut mac = mac(delta);
        assert!(mac.receive_ready(m(300), &ready()).is_ok());
    }
    for delta in [5800, 5801, u64::MAX] {
        assert!(matches!(
            mac(delta).receive_ready(m(300), &ready()),
            Err(HandshakeError::Deadline { .. })
        ));
    }
    for receive in [6100, 6101] {
        assert!(matches!(
            mac(0).receive_ready(m(receive), &ready()),
            Err(HandshakeError::Deadline {
                side: ClockSide::Mac,
                ..
            })
        ));
    }
    for prep in [1100, 1099, 7101, 6800] {
        let mut r = ready();
        let BootstrapMessage::Ready(v) = &mut r.message else {
            panic!()
        };
        v.preparation_deadline_ns = prep;
        assert!(
            matches!(
                mac(10).receive_ready(m(300), &r),
                Err(HandshakeError::Protocol { .. })
            ),
            "{prep}"
        );
    }
    let mut r = ready();
    let BootstrapMessage::Ready(v) = &mut r.message else {
        panic!()
    };
    v.preparation_deadline_ns = 6890;
    assert!(mac(10).receive_ready(m(300), &r).is_ok());
    for deadline in [1200, 1199, 7001] {
        let mut a = arm();
        let BootstrapMessage::Arm(v) = &mut a.message else {
            panic!()
        };
        v.deadline_ns = deadline;
        let mut s = supervisor();
        s.ready(l(1100)).unwrap();
        assert!(s.receive_arm(l(1200), &a).is_err());
    }
    for now in [6890, 6891] {
        let mut s = armed();
        assert!(matches!(
            s.query_complete(l(now), &arm().binding, QUERY),
            Err(HandshakeError::Deadline {
                side: ClockSide::Supervisor,
                ..
            })
        ));
    }
    let mut s = supervisor();
    assert!(matches!(
        s.ready(l(7000)),
        Err(HandshakeError::Deadline { .. })
    ));
}
#[test]
fn overflow_rollback_and_zero_window_are_explicit_and_sticky() {
    assert!(matches!(
        MacHandshake::new(
            start(),
            m(u64::MAX),
            0,
            ExpectedReadyDeclaration {
                boot_digest: [7; 32],
                namespace_digest: [8; 32]
            },
            window()
        ),
        Err(HandshakeError::ClockOverflow {
            side: ClockSide::Mac
        })
    ));
    assert!(matches!(
        SupervisorHandshake::new(start(), l(u64::MAX), local(), window()),
        Err(HandshakeError::ClockOverflow {
            side: ClockSide::Supervisor
        })
    ));
    assert!(matches!(
        SupervisorHandshake::new(start(), l(0), local(), HandshakeWindow { wall_clock_ns: 0 }),
        Err(HandshakeError::Window)
    ));
    let mut r = ready();
    let BootstrapMessage::Ready(v) = &mut r.message else {
        panic!()
    };
    v.linux_ready_ns = u64::MAX - 10;
    v.preparation_deadline_ns = u64::MAX;
    assert!(matches!(
        mac(10).receive_ready(m(300), &r),
        Err(HandshakeError::ClockOverflow {
            side: ClockSide::Supervisor
        })
    ));
    let mut mac = mac(10);
    mac.tick(m(200)).unwrap();
    let error = mac.tick(m(199)).unwrap_err();
    assert!(matches!(
        error,
        HandshakeError::ClockRollback {
            side: ClockSide::Mac,
            ..
        }
    ));
    assert_eq!(mac.receive_ready(m(300), &ready()), Err(error));
    let mut s = armed();
    let error = s.tick(l(1199)).unwrap_err();
    assert!(matches!(
        error,
        HandshakeError::ClockRollback {
            side: ClockSide::Supervisor,
            ..
        }
    ));
    assert_eq!(s.query_complete(l(1300), &arm().binding, QUERY), Err(error));
}
