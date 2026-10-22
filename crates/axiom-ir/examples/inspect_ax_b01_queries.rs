//! 只读尺寸诊断：真实生成原容量 query，估算短名字 / 死定义 / 相同项共享的尺寸。
//! 不改生产 query、不输出改写的 SMT、不规划请求或运行 solver。
use radishaxiom_ir::{
    document::check_canonical_document,
    json::JsonLimits,
    obligations::{ObligationLimits, ObligationProfile, generate_obligations},
    query::{GeneratorIdentity, QueryError, QueryLimits, QueryProfile, encode_query},
};
use std::{collections::BTreeMap, error::Error, io::Write, path::PathBuf};

struct Command {
    symbol: bool,
    bytes: usize,
    occurrences: usize,
    dependencies: Vec<usize>,
}
struct Sizes {
    terms: usize,
    occurrences: usize,
    live_definitions: usize,
    short_names_bytes: usize,
    live_bytes: usize,
    live_short_names_bytes: usize,
    shared_terms: usize,
    shared_short_names_bytes: usize,
    shared_live_short_names_bytes: usize,
}

fn references(line: &str, prefix: &str) -> Result<Vec<usize>, Box<dyn Error>> {
    line.split(|c: char| c.is_ascii_whitespace() || c == '(' || c == ')')
        .filter_map(|token| token.strip_prefix(prefix))
        .map(|index| Ok(index.parse()?))
        .collect()
}

fn sizes(bytes: &[u8], prefix: &str, symbols: usize) -> Result<Sizes, Box<dyn Error>> {
    let text = std::str::from_utf8(bytes)?;
    let mut commands = Vec::new();
    let mut tail_bytes = 0;
    let mut tail_occurrences = 0;
    let mut goal = None;
    for line in text.split_inclusive('\n') {
        let refs = references(line, prefix)?;
        if line.starts_with("(define-fun ") || line.starts_with("(declare-const ") {
            let (&id, dependencies) = refs.split_first().ok_or("missing term name")?;
            if id != commands.len() || dependencies.iter().any(|&dep| dep >= id) {
                return Err("query is not a topological, dense term DAG".into());
            }
            commands.push(Command {
                symbol: line.starts_with("(declare-const "),
                bytes: line.len(),
                occurrences: refs.len(),
                dependencies: dependencies.to_vec(),
            });
        } else {
            tail_bytes += line.len();
            tail_occurrences += refs.len();
            if line.starts_with("(assert ") {
                if refs.len() != 1 || goal.replace(refs[0]).is_some() {
                    return Err("expected one asserted term".into());
                }
            } else if !refs.is_empty() {
                return Err("unexpected term reference outside DAG / assert".into());
            }
        }
    }
    if commands.iter().filter(|c| c.symbol).count() != symbols {
        return Err("free symbol catalogue differs from declarations".into());
    }
    let mut live = vec![false; commands.len()];
    let mut stack = vec![goal.ok_or("missing assert")?];
    while let Some(id) = stack.pop() {
        let marker = live.get_mut(id).ok_or("unknown term")?;
        if !*marker {
            *marker = true;
            stack.extend_from_slice(&commands[id].dependencies);
        }
    }
    let occurrences = commands.iter().map(|c| c.occurrences).sum::<usize>() + tail_occurrences;
    let kept = commands
        .iter()
        .enumerate()
        .filter(|(id, command)| command.symbol || live[*id]);
    let live_bytes = tail_bytes + kept.clone().map(|(_, c)| c.bytes).sum::<usize>();
    let live_occurrences =
        tail_occurrences + kept.clone().map(|(_, c)| c.occurrences).sum::<usize>();
    // 唯一尺寸假设：q<64hex>_tN 换成 tN，序号不变；保留全部自由符号。
    let saving_per_name = prefix.len() - 1;
    let shared = shared_sizes(text, prefix)?;
    Ok(Sizes {
        terms: commands.len(),
        occurrences,
        live_definitions: kept.filter(|(_, c)| !c.symbol).count(),
        short_names_bytes: bytes.len() - saving_per_name * occurrences,
        live_bytes,
        live_short_names_bytes: live_bytes - saving_per_name * live_occurrences,
        shared_terms: shared.0,
        shared_short_names_bytes: shared.1,
        shared_live_short_names_bytes: shared.2,
    })
}

fn shared_sizes(text: &str, prefix: &str) -> Result<(usize, usize, usize), Box<dyn Error>> {
    // 仅估算相同 sort / 运算符 / 有序前提的共享，不交换参数或做代数化简。
    // 自由符号始终各有独立身份；所有引用替换为其首次出现的代表。
    let mut representatives = Vec::new();
    let mut definitions = BTreeMap::new();
    let mut commands = Vec::new();
    let mut tail_bytes = 0;
    let mut goal = None;
    for line in text.split_inclusive('\n') {
        if let Some(body) = line.strip_prefix("(declare-const ") {
            let (_, sort) = body
                .trim_end()
                .trim_end_matches(')')
                .split_once(' ')
                .ok_or("symbol sort")?;
            let id = commands.len();
            representatives.push(id);
            commands.push(Command {
                symbol: true,
                bytes: "(declare-const t".len()
                    + id.to_string().len()
                    + 1
                    + sort.len()
                    + ")\n".len(),
                occurrences: 1,
                dependencies: Vec::new(),
            });
        } else if line.starts_with("(define-fun ") {
            let (_, body) = line.split_once(" () ").ok_or("definition sort")?;
            let body = body.strip_suffix(")\n").ok_or("definition delimiter")?;
            let mut key = String::new();
            let mut dependencies = Vec::new();
            for piece in
                body.split_inclusive(|c: char| c.is_ascii_whitespace() || c == '(' || c == ')')
            {
                let token = piece
                    .trim_end_matches(|c: char| c.is_ascii_whitespace() || c == '(' || c == ')');
                if let Some(index) = token.strip_prefix(prefix) {
                    let original: usize = index.parse()?;
                    let &representative = representatives
                        .get(original)
                        .ok_or("shared forward reference")?;
                    key.push('t');
                    key.push_str(&representative.to_string());
                    key.push_str(&piece[token.len()..]);
                    dependencies.push(representative);
                } else {
                    key.push_str(piece);
                }
            }
            let id = if let Some(&id) = definitions.get(&key) {
                id
            } else {
                let id = commands.len();
                commands.push(Command {
                    symbol: false,
                    bytes: "(define-fun t".len()
                        + id.to_string().len()
                        + " () ".len()
                        + key.len()
                        + ")\n".len(),
                    occurrences: 1 + dependencies.len(),
                    dependencies,
                });
                definitions.insert(key, id);
                id
            };
            representatives.push(id);
        } else if line.starts_with("(assert ") {
            let refs = references(line, prefix)?;
            let &original = refs.first().ok_or("shared assert")?;
            let id = representatives[original];
            goal = Some(id);
            tail_bytes += "(assert t".len() + id.to_string().len() + ")\n".len();
        } else {
            tail_bytes += line.len();
        }
    }
    let mut live = vec![false; commands.len()];
    let mut stack = vec![goal.ok_or("shared missing assert")?];
    while let Some(id) = stack.pop() {
        if !live[id] {
            live[id] = true;
            stack.extend_from_slice(&commands[id].dependencies);
        }
    }
    let all_bytes = tail_bytes + commands.iter().map(|c| c.bytes).sum::<usize>();
    let live_bytes = tail_bytes
        + commands
            .iter()
            .enumerate()
            .filter(|(id, c)| c.symbol || live[*id])
            .map(|(_, c)| c.bytes)
            .sum::<usize>();
    Ok((commands.len(), all_bytes, live_bytes))
}

fn main() -> Result<(), Box<dyn Error>> {
    let root = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../..");
    let ir_json = JsonLimits {
        max_input_bytes: 16_000_000,
        max_values: 2_000_000,
        max_nesting: 128,
    };
    let query_limits = QueryLimits {
        ir_json,
        max_input_slots: 10_000,
        max_value_cells: 10_000_000,
        max_expression_instances: 1_000_000,
        max_slot_comparisons: 1_000_000,
        max_smt_nodes: 10_000_000,
        max_output_bytes: 100_000_000,
    };
    let generator = GeneratorIdentity::new(&format!("sha256:{}", "a".repeat(64)))?;
    let mut output = std::io::BufWriter::new(std::io::stdout().lock());
    writeln!(
        output,
        "candidate\tir_path\tir_raw\tp2_raw\tprofile\tkind\ttarget\tquery_raw\tquery_bytes\tfree_symbols\tterms\tname_occurrences\tlive_definitions\tshort_names_bytes\tlive_bytes\tlive_short_names_bytes\tshared_terms\tshared_short_names_bytes\tshared_live_short_names_bytes"
    )?;
    let mut total = 0;
    for line in include_str!("../../../contracts/ir-derived-obligations-v0.2/cases.tsv").lines() {
        let columns: Vec<_> = line.split('\t').collect();
        if !columns[0].starts_with("ax-b01-") {
            continue;
        }
        let document = check_canonical_document(&std::fs::read(root.join(columns[1]))?, ir_json)?;
        let set = generate_obligations(
            &document,
            ObligationProfile::VerificationV0_2,
            ObligationLimits {
                ir_json,
                max_obligations: 100_000,
                max_definition_bytes: 16_000_000,
                max_path_bytes: 8_000_000,
                max_output_bytes: 24_000_000,
            },
        )?;
        for profile in [
            QueryProfile::MapFilterV0_1,
            QueryProfile::MapFilterV0_2,
            QueryProfile::MapFilterV0_3,
            QueryProfile::MapFilterV0_4,
        ] {
            for target in set.obligations() {
                let query = match encode_query(
                    profile,
                    &document,
                    &set,
                    target.id(),
                    &generator,
                    query_limits,
                ) {
                    Ok(query) => query,
                    Err(QueryError::NotProve(_) | QueryError::UnsupportedKind(_)) => continue,
                    Err(error) => return Err(error.into()),
                };
                let measured = sizes(
                    query.bytes(),
                    &format!("q{}_t", &target.id()[7..]),
                    query.symbols().len(),
                )?;
                writeln!(
                    output,
                    "{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}",
                    columns[0],
                    columns[1],
                    query.binding().ir_artifact(),
                    set.artifact_digest(),
                    profile.as_str(),
                    target.kind().as_str(),
                    target.id(),
                    query.artifact_digest(),
                    query.bytes().len(),
                    query.symbols().len(),
                    measured.terms,
                    measured.occurrences,
                    measured.live_definitions,
                    measured.short_names_bytes,
                    measured.live_bytes,
                    measured.live_short_names_bytes,
                    measured.shared_terms,
                    measured.shared_short_names_bytes,
                    measured.shared_live_short_names_bytes,
                )?;
                total += 1;
            }
        }
    }
    output.flush()?;
    if total != 72 {
        return Err(format!("expected 72 original queries, observed {total}").into());
    }
    Ok(())
}
