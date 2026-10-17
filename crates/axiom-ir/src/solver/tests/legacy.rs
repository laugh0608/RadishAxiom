//! 基线由 git archive 14a9693 的原始实现于 2026-10-17 导出；
//! 使用 tests.rs 固定合成 generator/tool、旧 limits 与 synthetic(false)，不执行 solver。
//! 复现旧来源：git archive 14a9693 到专用空目录，将本文件复制到其
//! solver/tests/legacy.rs 并在旧 tests.rs 添加 `mod legacy;`；在该快照运行
//! RADISHAXIOM_P4_BASELINE_DIR=<新的绝对输出目录> cargo +1.97.1 test
//! -p radishaxiom-ir --lib solver::tests::legacy::export_legacy_materials
//! --locked --offline -- --ignored。输出目录必须不存在；不启动 solver。
use super::*;

const CASES: [(&str, [&str; 6]); 3] = [
    (
        "contracts/map-filter-query-v0.1/inputs/minimal.jcs",
        [
            "sha256:dfeaa29dd38502586061dce94a697842fa95c4e4f16b1d9eafa1a0583f98181e",
            "sha256:5f09419cf7c2b4befd486c96516188da1370673a1482bb396a79b2ed41059f77",
            "sha256:e77dc7636a279ca29a28fba64ee197aed05e381d3b3550ed51f36ce72fbb5366",
            "sha256:71654c71986d30921d4db9c7aef92652e583caec36cc3409282a48926e6dba45",
            "sha256:5a57ba694f7ef626bb8d99341ebc2a7123bdf4f2adfcea1d4716e6660175af01",
            "sha256:bf5417954e09e0c3787adf15d7a0f1f9755afb05e980c3f39de074b18edac5a1",
        ],
    ),
    (
        "contracts/map-filter-query-v0.1/inputs/unicode-literals.jcs",
        [
            "sha256:c7a7747fe1d68c7bd3c11bebc103897949aa29f28c30b1fdc90a10430a8a8ca7",
            "sha256:9d5d8cd79191e7c1cfd0936dd00635dcdb46d07299dce582f1cece684caa692e",
            "sha256:b24727ce2a59ff64a503f5cf722e916ebd8a05eedc8c343e33bde21ecf880f57",
            "sha256:d381c6102cb9e4b3bc8700d947a43f1b10ae41a5cf2328534a49b3edfb6e7051",
            "sha256:2088dddb45a32f87abfe7fa4bb31be3842fd54f449fbe9edf8f18e59602a3f8b",
            "sha256:f75eb6c7ecdc4e573b71ddb01ad88fd1f25c86320e668aa604474c2101981bfb",
        ],
    ),
    (
        "contracts/solver-model-v0.1/inputs/composite.jcs",
        [
            "sha256:f2da0cfcf30e7133a5accb3600a72478f2590412eee15447c27f5e39c2369e64",
            "sha256:ad86344f63422732a0e7908114c33ee6752b03debd28f72a62a8144d922fecaa",
            "sha256:54a6614bd8afc739ec9e06298f5dae1db64b4fcbcd482a61c42152799b946dfb",
            "sha256:75736f985bce154d0d7c7c11791469cf42cf241ba6efd4e086ca4a84157be0ed",
            "sha256:115c6bc666c8ba27b191c1244ff4a700d8c925d367176e844ffb17bbf73a8de6",
            "sha256:9186883d42dfa1870ddacaa6e83e06edec364bd1a0a327e1a44fb43b5e033bb0",
        ],
    ),
];

#[test]
fn legacy_bytes_match_pre_compaction_14a9693_baseline() {
    for (path, hashes) in CASES {
        let l = limits();
        let (d, set, q) = setup(path, l);
        let req = plan(&d, &set, &q, l).unwrap();
        let source = synthetic(&req, false);
        let response =
            parse_solver_response(&req, super::response(&req, source.as_bytes())).unwrap();
        let candidate = decode_model_world(&req, response.sat_model().unwrap()).unwrap();
        for ((name, bytes), expected) in [
            ("query", req.stdin_bytes()),
            ("symbols", req.symbol_bytes()),
            ("layout", req.layout_bytes()),
            ("request", req.canonical_bytes()),
            ("response", response.canonical_bytes()),
            ("candidate", candidate.canonical_bytes()),
        ]
        .into_iter()
        .zip(hashes)
        {
            assert_eq!(
                crate::obligations::raw_digest(bytes),
                expected,
                "{path} {name}"
            );
        }
    }
}

/// 明确调用的可复现审计入口；正常测试只核对冻结摘要，不写文件。
#[test]
#[ignore = "explicit legacy artifact export into a new directory"]
fn export_legacy_materials() {
    legacy_bytes_match_pre_compaction_14a9693_baseline();
    let destination = PathBuf::from(
        std::env::var_os("RADISHAXIOM_P4_BASELINE_DIR")
            .expect("RADISHAXIOM_P4_BASELINE_DIR must name a new absolute directory"),
    );
    assert!(destination.is_absolute());
    std::fs::create_dir(&destination).unwrap();
    let mut manifest = String::from(
        "baseline=14a9693\nprofile=axiom-p4-cvc5-1.3.4-query0.2-model-v0.1\nmodel=tests::synthetic(false)\ngenerator=sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\ntool=macos-arm64/payload-bx64/acceptance-cx64 (synthetic)\n",
    );
    for (path, _) in CASES {
        let l = limits();
        let (d, set, q) = setup(path, l);
        let req = plan(&d, &set, &q, l).unwrap();
        let source = synthetic(&req, false);
        let response =
            parse_solver_response(&req, super::response(&req, source.as_bytes())).unwrap();
        let candidate = decode_model_world(&req, response.sat_model().unwrap()).unwrap();
        let case = destination.join(path.replace('/', "_"));
        std::fs::create_dir(&case).unwrap();
        for (name, bytes) in [
            ("ir", d.canonical_bytes()),
            ("p2", set.canonical_bytes()),
            ("query", req.stdin_bytes()),
            ("symbols", req.symbol_bytes()),
            ("layout", req.layout_bytes()),
            ("request", req.canonical_bytes()),
            ("stdout", source.as_bytes()),
            ("response", response.canonical_bytes()),
            ("candidate", candidate.canonical_bytes()),
        ] {
            std::fs::write(case.join(name), bytes).unwrap();
            manifest.push_str(&format!(
                "{path}\t{name}\t{}\n",
                crate::obligations::raw_digest(bytes)
            ));
        }
    }
    std::fs::write(destination.join("manifest.txt"), manifest).unwrap();
}
