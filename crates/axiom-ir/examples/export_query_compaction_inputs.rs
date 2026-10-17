//! 本地尺寸可行性诊断输入导出；原容量、原 SMT、完整符号来源，不运行 solver。
//! 用法：export_query_compaction_inputs [--production] [--corpus] <不存在的仓库 .tmp 子目录>。
use radishaxiom_ir::{
    document::{CanonicalDocument, check_canonical_document},
    json::{JsonLimits, canonicalize_json},
    obligations::{
        Obligation, ObligationLimits, ObligationProfile, ObligationSet, generate_obligations,
    },
    query::{
        CompactQueryLimits, EncodedQuery, GeneratorIdentity, QueryError, QueryLimits, QueryProfile,
        SymbolOrigin, encode_query,
    },
};
use std::{
    collections::BTreeMap,
    error::Error,
    fmt::Write as _,
    fs::{self, OpenOptions},
    io::Write as _,
    path::{Component, Path, PathBuf},
    process::Command,
};

type Result<T> = std::result::Result<T, Box<dyn Error>>;
const GENERATOR: &str = "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
const PROFILES: [QueryProfile; 4] = [
    QueryProfile::MapFilterV0_1,
    QueryProfile::MapFilterV0_2,
    QueryProfile::MapFilterV0_3,
    QueryProfile::MapFilterV0_4,
];

fn json_limits() -> JsonLimits {
    JsonLimits {
        max_input_bytes: 16_000_000,
        max_values: 2_000_000,
        max_nesting: 128,
    }
}
fn query_limits() -> QueryLimits {
    QueryLimits {
        ir_json: json_limits(),
        max_input_slots: 10_000,
        max_value_cells: 10_000_000,
        max_expression_instances: 1_000_000,
        max_slot_comparisons: 1_000_000,
        max_smt_nodes: 10_000_000,
        max_output_bytes: 100_000_000,
    }
}
// Explicit local diagnostic ceilings; these do not change P4 stdin or production defaults.
fn production_query_limits() -> QueryLimits {
    QueryLimits {
        max_output_bytes: 1_048_576,
        ..query_limits()
    }
}
fn compact_limits() -> CompactQueryLimits {
    CompactQueryLimits {
        max_normalized_nodes: 1_000_000,
        max_normalized_edges: 5_000_000,
        max_scratch_cells: 100_000_000,
        max_work_steps: 2_000_000_000,
        max_temporary_bytes: 1_000_000_000,
        max_integer_digits: 4096,
        max_dag_depth: 100_000,
    }
}
fn base_limits_json(limits: QueryLimits) -> String {
    format!(
        "{{\"ir_json\":{{\"max_input_bytes\":{},\"max_values\":{},\"max_nesting\":{}}},\"max_input_slots\":{},\"max_value_cells\":{},\"max_expression_instances\":{},\"max_slot_comparisons\":{},\"max_smt_nodes\":{},\"max_output_bytes\":{}}}",
        limits.ir_json.max_input_bytes,
        limits.ir_json.max_values,
        limits.ir_json.max_nesting,
        limits.max_input_slots,
        limits.max_value_cells,
        limits.max_expression_instances,
        limits.max_slot_comparisons,
        limits.max_smt_nodes,
        limits.max_output_bytes
    )
}
fn compact_limits_json(limits: CompactQueryLimits) -> String {
    format!(
        "{{\"max_normalized_nodes\":{},\"max_normalized_edges\":{},\"max_scratch_cells\":{},\"max_work_steps\":{},\"max_temporary_bytes\":{},\"max_integer_digits\":{},\"max_dag_depth\":{}}}",
        limits.max_normalized_nodes,
        limits.max_normalized_edges,
        limits.max_scratch_cells,
        limits.max_work_steps,
        limits.max_temporary_bytes,
        limits.max_integer_digits,
        limits.max_dag_depth
    )
}
fn usage(query: &EncodedQuery) -> String {
    let u = query.usage();
    format!(
        "{{\"input_slots\":{},\"value_cells\":{},\"expression_instances\":{},\"slot_comparisons\":{},\"smt_nodes\":{},\"output_bytes\":{}}}",
        u.input_slots,
        u.value_cells,
        u.expression_instances,
        u.slot_comparisons,
        u.smt_nodes,
        u.output_bytes
    )
}
fn compact_usage(query: &EncodedQuery) -> String {
    let u = query.compact_usage().expect("production query usage");
    format!(
        "{{\"normalized_nodes\":{},\"normalized_edges\":{},\"scratch_cells\":{},\"work_steps\":{},\"temporary_bytes\":{},\"integer_digits\":{},\"dag_depth\":{}}}",
        u.normalized_nodes,
        u.normalized_edges,
        u.scratch_cells,
        u.work_steps,
        u.temporary_bytes,
        u.integer_digits,
        u.dag_depth
    )
}
fn load(root: &Path, path: &str) -> Result<(CanonicalDocument, ObligationSet)> {
    if Path::new(path)
        .components()
        .any(|c| !matches!(c, Component::Normal(_)))
    {
        return Err(format!("expected repository-relative input path: {path}").into());
    }
    let document = check_canonical_document(&fs::read(root.join(path))?, json_limits())?;
    let set = generate_obligations(
        &document,
        ObligationProfile::VerificationV0_2,
        ObligationLimits {
            ir_json: json_limits(),
            max_obligations: 100_000,
            max_definition_bytes: 16_000_000,
            max_path_bytes: 8_000_000,
            max_output_bytes: 24_000_000,
        },
    )?;
    Ok((document, set))
}

// 与测试导出一致：slot / component 是字符串，None component 为 "active"。
fn quoted(value: &str) -> String {
    let mut text = String::from("\"");
    for c in value.chars() {
        match c {
            '"' => text.push_str("\\\""),
            '\\' => text.push_str("\\\\"),
            c if c <= '\u{1f}' => write!(text, "\\u{:04x}", u32::from(c)).unwrap(),
            c => text.push(c),
        }
    }
    text.push('"');
    text
}
fn symbols(query: &EncodedQuery) -> String {
    let entries: Vec<_> = query
        .symbols()
        .iter()
        .map(|symbol| {
            let origin = match symbol.origin() {
                SymbolOrigin::TextLiteral(value) => {
                    format!("{{\"kind\":\"text\",\"value\":{}}}", quoted(value))
                }
                SymbolOrigin::Input {
                    interface,
                    slot,
                    component,
                } => format!(
                    "{{\"kind\":\"input\",\"interface\":{},\"slot\":{},\"component\":{}}}",
                    quoted(interface),
                    quoted(&slot.to_string()),
                    quoted(
                        &component
                            .map(|n| n.to_string())
                            .unwrap_or_else(|| "active".to_owned())
                    )
                ),
            };
            format!(
                "{{\"name\":{},\"sort\":{},\"origin\":{origin}}}",
                quoted(symbol.name()),
                quoted(symbol.sort())
            )
        })
        .collect();
    format!("[{}]\n", entries.join(","))
}
fn create_file(path: &Path, bytes: &[u8]) -> Result<()> {
    OpenOptions::new()
        .write(true)
        .create_new(true)
        .open(path)?
        .write_all(bytes)?;
    Ok(())
}

struct Export {
    production: bool,
    directory: PathBuf,
    generator: GeneratorIdentity,
    unique: BTreeMap<String, (usize, String)>,
    rows: Vec<String>,
}
struct Source<'a> {
    candidate: &'a str,
    ir_path: &'a str,
    corpus: Option<(&'a str, usize)>,
}
impl Export {
    fn add(
        &mut self,
        source: &Source<'_>,
        profile: QueryProfile,
        target: &Obligation,
        set: &ObligationSet,
        query: &EncodedQuery,
        legacy: Option<(QueryProfile, &EncodedQuery)>,
    ) -> Result<()> {
        let digest = query.artifact_digest();
        let hex = digest
            .strip_prefix("sha256:")
            .ok_or("query digest prefix")?;
        if hex.len() != 64 || !hex.bytes().all(|b| b.is_ascii_hexdigit()) {
            return Err("invalid query digest filename".into());
        }
        let smt_path = format!("{hex}.smt2");
        // Compact text may coincide across distinct bindings; keep each original origin map.
        let symbols_hex = legacy.map_or(hex, |(_, old)| &old.artifact_digest()[7..]);
        let symbols_path = format!("{symbols_hex}.symbols.json");
        let symbol_json = symbols(query);
        if let Some((bytes, previous_symbols)) = self.unique.get(digest) {
            if *bytes != query.bytes().len()
                || (!self.production && previous_symbols != &symbol_json)
                || fs::read(self.directory.join(&smt_path))? != query.bytes()
            {
                return Err(format!("inconsistent duplicate raw query: {digest}").into());
            }
        } else {
            create_file(&self.directory.join(&smt_path), query.bytes())?;
            if !self.production {
                create_file(&self.directory.join(&symbols_path), symbol_json.as_bytes())?;
            }
            self.unique.insert(
                digest.to_owned(),
                (query.bytes().len(), symbol_json.clone()),
            );
        }
        if self.production {
            let path = self.directory.join(&symbols_path);
            match fs::read(&path) {
                Ok(previous) if previous == symbol_json.as_bytes() => {}
                Ok(_) => return Err("inconsistent symbols for original query identity".into()),
                Err(error) if error.kind() == std::io::ErrorKind::NotFound => {
                    create_file(&path, symbol_json.as_bytes())?
                }
                Err(error) => return Err(error.into()),
            }
        }
        let definition = std::str::from_utf8(target.canonical_definition())?;
        let mut row = format!(
            "{{\"candidate\":{},\"ir_path\":{},\"ir_raw\":{},\"p2_raw\":{},\"profile\":{},\"kind\":{},\"target\":{},\"definition\":{definition},\"query_raw\":{},\"query_bytes\":{},\"smt_path\":{},\"symbols_path\":{}",
            quoted(source.candidate),
            quoted(source.ir_path),
            quoted(query.binding().ir_artifact()),
            quoted(set.artifact_digest()),
            quoted(profile.as_str()),
            quoted(target.kind().as_str()),
            quoted(target.id()),
            quoted(digest),
            query.bytes().len(),
            quoted(&smt_path),
            quoted(&symbols_path)
        );
        if let Some((corpus_path, index)) = source.corpus {
            write!(
                row,
                ",\"corpus_path\":{},\"case_name\":{},\"target_index\":{index}",
                quoted(corpus_path),
                quoted(source.candidate)
            )?;
        }
        if let Some((previous_profile, legacy)) = legacy {
            let old = legacy.usage();
            let new = query.usage();
            if (
                old.input_slots,
                old.value_cells,
                old.expression_instances,
                old.slot_comparisons,
                old.smt_nodes,
            ) != (
                new.input_slots,
                new.value_cells,
                new.expression_instances,
                new.slot_comparisons,
                new.smt_nodes,
            ) {
                return Err("compact changed original construction usage".into());
            }
            write!(
                row,
                ",\"legacy_profile\":{},\"legacy_query_raw\":{},\"legacy_query_bytes\":{},\"legacy_symbols\":{},\"legacy_usage\":{},\"usage\":{},\"compact_usage\":{},\"query_rules\":{}",
                quoted(previous_profile.as_str()),
                quoted(legacy.artifact_digest()),
                legacy.bytes().len(),
                symbols(legacy).trim(),
                usage(legacy),
                usage(query),
                compact_usage(query),
                quoted(query.binding().query_rules().ok_or("missing query rules")?)
            )?;
        }
        row.push('}');
        self.rows.push(row);
        Ok(())
    }
    fn ax_b01(&mut self, root: &Path) -> Result<()> {
        for line in include_str!("../../../contracts/ir-derived-obligations-v0.2/cases.tsv").lines()
        {
            let columns: Vec<_> = line.split('\t').collect();
            if !matches!(
                columns[0],
                "ax-b01-correct" | "ax-b01-wrong-add" | "ax-b01-wrong-drop-zero"
            ) {
                continue;
            }
            let (document, set) = load(root, columns[1])?;
            let source = Source {
                candidate: columns[0],
                ir_path: columns[1],
                corpus: None,
            };
            let profiles = if self.production {
                vec![QueryProfile::MapFilterV0_4]
            } else {
                PROFILES.to_vec()
            };
            for profile in profiles {
                for target in set.obligations() {
                    let query = match encode_query(
                        profile,
                        &document,
                        &set,
                        target.id(),
                        &self.generator,
                        query_limits(),
                    ) {
                        Ok(query) => query,
                        Err(QueryError::NotProve(_) | QueryError::UnsupportedKind(_)) => continue,
                        Err(error) => return Err(error.into()),
                    };
                    if self.production {
                        let compact = encode_query(
                            QueryProfile::MapFilterV0_5,
                            &document,
                            &set,
                            target.id(),
                            &self.generator,
                            production_query_limits().with_compact(compact_limits()),
                        )?;
                        self.add(
                            &source,
                            QueryProfile::MapFilterV0_5,
                            target,
                            &set,
                            &compact,
                            Some((profile, &query)),
                        )?;
                    } else {
                        self.add(&source, profile, target, &set, &query, None)?;
                    }
                }
            }
        }
        if self.rows.len() != if self.production { 27 } else { 72 }
            || self.unique.len() != if self.production { 24 } else { 27 }
        {
            return Err(format!(
                "expected {} rows / {} unique, got {} / {}",
                if self.production { 27 } else { 72 },
                if self.production { 24 } else { 27 },
                self.rows.len(),
                self.unique.len()
            )
            .into());
        }
        Ok(())
    }
    fn corpus(&mut self, root: &Path) -> Result<()> {
        // 同现有语义测试：Python 只投影含 number/null 的只读材料，不生成世界或请求。
        // TSV 字段拒绝分隔符；definition 由标准 JSON 编码，随后核对 P2 规范字节。
        const INDEX: &str = r#"import json,sys
d=json.load(open(sys.argv[1],encoding='utf-8'))
for c in d['cases']:
    for i,t in enumerate(c['targets']):
        fields=[c['name'],c['ir'],c['ir_raw'],str(i),t['id'],json.dumps(t['definition'],ensure_ascii=False,separators=(',',':'))]
        assert all(isinstance(f,str) and not any(x in f for x in '\t\r\n') for f in fields)
        print('\t'.join(fields))
"#;
        for (index, profile) in PROFILES.into_iter().enumerate() {
            let path = format!("contracts/map-filter-query-v0.{}/cases.json", index + 1);
            let output = Command::new("python3")
                .arg("-c")
                .arg(INDEX)
                .arg(root.join(&path))
                .output()?;
            if !output.status.success() {
                return Err(format!(
                    "corpus index {path}: {}",
                    String::from_utf8_lossy(&output.stderr)
                )
                .into());
            }
            let manifest = String::from_utf8(output.stdout)?;
            let mut current_path = String::new();
            let mut loaded = None;
            for line in manifest.lines() {
                let fields: Vec<_> = line.split('\t').collect();
                if fields.len() != 6 {
                    return Err(format!("invalid corpus index: {path}").into());
                }
                if current_path != fields[1] {
                    loaded = Some(load(root, fields[1])?);
                    current_path = fields[1].to_owned();
                }
                let (document, set) = loaded.as_ref().ok_or("empty corpus input path")?;
                if set.ir_artifact() != fields[2] {
                    return Err(format!("corpus IR raw mismatch: {path}/{}", fields[0]).into());
                }
                let target = set
                    .obligations()
                    .iter()
                    .find(|o| o.id() == fields[4])
                    .ok_or("corpus target absent from P2")?;
                if canonicalize_json(fields[5].as_bytes(), json_limits())?
                    != target.canonical_definition()
                {
                    return Err(format!("corpus definition mismatch: {path}/{}", fields[0]).into());
                }
                let query = encode_query(
                    profile,
                    document,
                    set,
                    target.id(),
                    &self.generator,
                    query_limits(),
                )?;
                let compact = if self.production {
                    Some(encode_query(
                        QueryProfile::MapFilterV0_5,
                        document,
                        set,
                        target.id(),
                        &self.generator,
                        production_query_limits().with_compact(compact_limits()),
                    )?)
                } else {
                    None
                };
                self.add(
                    &Source {
                        candidate: fields[0],
                        ir_path: fields[1],
                        corpus: Some((&path, fields[3].parse()?)),
                    },
                    if self.production {
                        QueryProfile::MapFilterV0_5
                    } else {
                        profile
                    },
                    target,
                    set,
                    compact.as_ref().unwrap_or(&query),
                    if self.production {
                        Some((profile, &query))
                    } else {
                        None
                    },
                )?;
            }
        }
        Ok(())
    }
}

fn main() -> Result<()> {
    let mut arguments = std::env::args_os().skip(1);
    let mut first = arguments.next().ok_or(
        "usage: export_query_compaction_inputs [--production] [--corpus] <new .tmp directory>",
    )?;
    let production = first == "--production";
    if production {
        first = arguments
            .next()
            .ok_or("missing production output directory")?;
    }
    let corpus = first == "--corpus";
    let destination = if corpus {
        arguments.next().ok_or("missing output directory")?
    } else {
        first
    };
    if arguments.next().is_some() {
        return Err("unexpected extra arguments".into());
    }
    let root = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("../..")
        .canonicalize()?;
    let requested = PathBuf::from(destination);
    let directory = if requested.is_absolute() {
        requested
    } else {
        std::env::current_dir()?.join(requested)
    };
    if directory
        .components()
        .any(|c| matches!(c, Component::ParentDir))
    {
        return Err("output must not contain parent traversal".into());
    }
    let temporary = root.join(".tmp").canonicalize()?;
    if !directory.starts_with(&temporary) || directory == temporary {
        return Err("output must be a new subdirectory of repository .tmp".into());
    }
    // 建立父目录前逐层检查已有节点，拒绝符号链接，不把输出重定向到 .tmp 之外。
    let mut parent = temporary.clone();
    let relative = directory.strip_prefix(&temporary)?;
    let components: Vec<_> = relative.components().collect();
    for component in &components[..components.len().saturating_sub(1)] {
        let Component::Normal(name) = component else {
            return Err("invalid output component".into());
        };
        parent.push(name);
        match fs::symlink_metadata(&parent) {
            Ok(metadata) if metadata.is_dir() && !metadata.file_type().is_symlink() => {}
            Ok(_) => return Err("output ancestor must be a real directory".into()),
            Err(error) if error.kind() == std::io::ErrorKind::NotFound => fs::create_dir(&parent)?,
            Err(error) => return Err(error.into()),
        }
    }
    fs::create_dir(&directory)?;
    let mut export = Export {
        production,
        directory,
        generator: GeneratorIdentity::new(GENERATOR)?,
        unique: BTreeMap::new(),
        rows: Vec::new(),
    };
    if corpus {
        export.corpus(&root)?;
    } else {
        export.ax_b01(&root)?;
    }
    let manifest = format!(
        "{{\"status\":{},\"generator\":{{\"digest\":{},\"status\":\"synthetic-diagnostic-identity-not-executable-hash\"}},{}\"rows\":[\n{}\n]}}\n",
        quoted(if production {
            "local-production-compact-query-not-proof-not-solver"
        } else {
            "local-feasibility-original-inputs-not-proof"
        }),
        quoted(GENERATOR),
        if production {
            format!(
                "\"limits\":{{\"base\":{},\"compact\":{},\"legacy_base\":{}}},",
                base_limits_json(production_query_limits()),
                compact_limits_json(compact_limits()),
                base_limits_json(query_limits())
            )
        } else {
            String::new()
        },
        export.rows.join(",\n")
    );
    create_file(&export.directory.join("manifest.json"), manifest.as_bytes())?;
    println!(
        "exported {} rows / {} unique raw queries to {}",
        export.rows.len(),
        export.unique.len(),
        export.directory.display()
    );
    Ok(())
}
