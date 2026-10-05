//! 逐行表达式的局部类型、保守标签推导与受限规范化。不求值、不证明算术范围或非干扰。

use std::collections::BTreeSet;
use std::fmt;

use crate::declarations::{
    self as decode, DeclarationError, DeclarationErrorKind, Label, ValueType,
};
use crate::json::{self, JsonLimits, Value};
use crate::normalization::{NormalizedDeclaration, NormalizedTypeDeclarations};

pub(crate) mod labels;
pub(crate) mod normalization;

/// 保守字段依赖标签；不是非干扰、总性或运行时安全结论。
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct RowLabelAnalysis {
    value_type: ValueType,
    label: Label,
}

impl RowLabelAnalysis {
    pub fn value_type(&self) -> &ValueType {
        &self.value_type
    }
    pub fn label(&self) -> Label {
        self.label
    }
}

/// 已检查支持范围和类型的逐行表达式；不含独立表达式摘要或证明结论。
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct NormalizedRowExpression {
    value_type: ValueType,
    canonical_bytes: Vec<u8>,
}

impl NormalizedRowExpression {
    pub fn value_type(&self) -> &ValueType {
        &self.value_type
    }
    pub fn canonical_bytes(&self) -> &[u8] {
        &self.canonical_bytes
    }
}

/// 仅描述逐行环境，不凭调用方给出的类型或标签缓存推导结果。
#[derive(Clone, Copy, Debug)]
pub enum RowScope<'a> {
    Closed,
    Single {
        record_type: &'a str,
    },
    Join {
        left_record_type: &'a str,
        right_record_type: &'a str,
    },
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum TypeErrorKind {
    UnknownOperator,
    ExpectedBoolean,
    ExpectedRecord,
    ExpectedOption,
    ExpectedInt,
    ExpectedFixed,
    ExpectedNumeric,
    TypeMismatch,
    ScaleMismatch,
    WrongArity,
    BoundOutOfRange,
    UnknownField,
    UnknownEnumMember,
    LiteralOutOfRange,
    ContractOperationInRow,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum UnsupportedTyping {
    /// IR 的 record.fields 元素结构和 is_some 机器 tag 尚待精确规范确认。
    UnspecifiedForm,
    /// 记录（含可选记录）的相等规则未纳入本组件的支持范围。
    RecordEquality,
    /// 不同范围的 Int 比较需确认类型兼容规则，不能自行添加隐式转换。
    MixedIntComparison,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub enum ExpressionError {
    Input(DeclarationError),
    Type {
        kind: TypeErrorKind,
        path: String,
    },
    Unsupported {
        reason: UnsupportedTyping,
        path: String,
    },
    UnknownScopeRecord {
        slot: usize,
        id: String,
    },
}

impl fmt::Display for ExpressionError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Input(error) => write!(f, "row expression input: {error}"),
            Self::Type { kind, path } => write!(f, "row expression {kind:?} at {path:?}"),
            Self::Unsupported { reason, path } => {
                write!(f, "row expression unsupported {reason:?} at {path:?}")
            }
            Self::UnknownScopeRecord { slot, id } => {
                write!(f, "unknown row scope record at slot {slot}: {id}")
            }
        }
    }
}

impl std::error::Error for ExpressionError {
    fn source(&self) -> Option<&(dyn std::error::Error + 'static)> {
        match self {
            Self::Input(error) => Some(error),
            _ => None,
        }
    }
}

impl From<DeclarationError> for ExpressionError {
    fn from(value: DeclarationError) -> Self {
        Self::Input(value)
    }
}

/// 接受已核对内容身份的声明；成员索引只构造一次，可用于同一图的多个表达式。
pub struct RowTypeChecker<'a> {
    types: &'a NormalizedTypeDeclarations,
    enum_members: Vec<BTreeSet<&'a str>>,
}

impl<'a> RowTypeChecker<'a> {
    pub fn new(types: &'a NormalizedTypeDeclarations) -> Self {
        let enum_members = types
            .enum_types()
            .iter()
            .map(|entry| {
                entry
                    .definition()
                    .members
                    .iter()
                    .map(String::as_str)
                    .collect()
            })
            .collect();
        Self {
            types,
            enum_members,
        }
    }

    /// input 是既有 IR 中一个表达式 object 的字节，不是新的公共制品格式。
    /// 成功只返回推导类型；不输出 proved、完整 IR 或可执行门控结果。
    pub fn infer(
        &self,
        input: &[u8],
        limits: JsonLimits,
        scope: RowScope<'_>,
    ) -> Result<ValueType, ExpressionError> {
        let value = json::parse(input, limits).map_err(DeclarationError::Json)?;
        self.infer_parsed(&value, "", scope)
    }

    /// 检查原始全部分支和操作数后，从声明重建保守标签；不接受标签缓存。
    pub fn analyze_labels(
        &self,
        input: &[u8],
        limits: JsonLimits,
        scope: RowScope<'_>,
    ) -> Result<RowLabelAnalysis, ExpressionError> {
        let value = json::parse(input, limits).map_err(DeclarationError::Json)?;
        let value_type = self.infer_parsed(&value, "", scope)?;
        let records = match scope {
            RowScope::Closed => vec![],
            RowScope::Single { record_type } => vec![record_type],
            RowScope::Join {
                left_record_type,
                right_record_type,
            } => {
                vec![left_record_type, right_record_type]
            }
        };
        let scopes: Vec<_> = records
            .into_iter()
            .map(|record_type| labels::RecordScope {
                record_type,
                fields: None,
            })
            .collect();
        let label = labels::LabelAnalyzer::new(self.types).analyze_checked(&value, &scopes);
        Ok(RowLabelAnalysis { value_type, label })
    }

    /// 先检查原输入全部表达式，再执行 IR 明确允许的结构规范化。
    /// 不做常量求值、算术重写、类型扩大或短路删除；未支持范围与 infer 相同。
    pub fn normalize(
        &self,
        input: &[u8],
        limits: JsonLimits,
        scope: RowScope<'_>,
    ) -> Result<NormalizedRowExpression, ExpressionError> {
        let mut value = json::parse(input, limits).map_err(DeclarationError::Json)?;
        let value_type = self.infer_parsed(&value, "", scope)?;
        normalization::normalize_checked(&mut value);
        let mut canonical_bytes = Vec::new();
        json::encode(&value, &mut canonical_bytes);
        Ok(NormalizedRowExpression {
            value_type,
            canonical_bytes,
        })
    }

    /// 节点检查复用有界文档树和原始 JSON Pointer，不重新编码 / 解析表达式。
    pub(crate) fn infer_parsed(
        &self,
        value: &Value,
        path: &str,
        scope: RowScope<'_>,
    ) -> Result<ValueType, ExpressionError> {
        let records = match scope {
            RowScope::Closed => Vec::new(),
            RowScope::Single { record_type } => vec![record_type],
            RowScope::Join {
                left_record_type,
                right_record_type,
            } => vec![left_record_type, right_record_type],
        };
        for (slot, id) in records.iter().enumerate() {
            if find(self.types.record_types(), id).is_none() {
                return Err(ExpressionError::UnknownScopeRecord {
                    slot,
                    id: (*id).to_owned(),
                });
            }
        }
        // 栈顶为索引 0；join 初始语义顺序仍是 [left_row, right_row]。
        let mut bindings = records
            .into_iter()
            .rev()
            .map(|id| ValueType::Record {
                record_type: id.to_owned(),
            })
            .collect();
        self.infer_value(value, path, &mut bindings)
    }

    fn annotation(&self, value: &Value, path: &str) -> Result<ValueType, ExpressionError> {
        let result = decode::value_type(value, path)?;
        let mut current = &result;
        let mut path = path.to_owned();
        while let ValueType::Option { inner } = current {
            current = inner;
            path.push_str("/inner");
        }
        let reference = match current {
            ValueType::Record { record_type } => Some((
                "record_type",
                find(self.types.record_types(), record_type).is_some(),
            )),
            ValueType::Enum { enum_type } => Some((
                "enum_type",
                find(self.types.enum_types(), enum_type).is_some(),
            )),
            _ => None,
        };
        if let Some((key, false)) = reference {
            return Err(decode::error(
                DeclarationErrorKind::UnresolvedReference,
                &decode::child(&path, key),
            )
            .into());
        }
        Ok(result)
    }

    fn infer_value(
        &self,
        value: &Value,
        path: &str,
        bindings: &mut Vec<ValueType>,
    ) -> Result<ValueType, ExpressionError> {
        let Value::Object(members) = value else {
            return Err(decode::error(DeclarationErrorKind::ExpectedObject, path).into());
        };
        let op_path = decode::child(path, "op");
        let op_value = members
            .iter()
            .find(|(key, _, _)| key == "op")
            .ok_or_else(|| decode::error(DeclarationErrorKind::MissingMember, &op_path))?;
        let op = decode::string(&op_value.1, &op_path)?;
        let keys: &[&str] = match op {
            "literal_bool" | "literal_text" | "some" | "not" => &["op", "value"],
            "literal_int" => &["op", "type", "value"],
            "literal_fixed" => &["coefficient", "op", "type"],
            "literal_enum" => &["enum_type", "member", "op"],
            "none" => &["op", "type"],
            "bound" => &["index", "op"],
            "field" => &["field", "op", "record"],
            "and" | "or" => &["op", "values"],
            "eq" | "lt" | "le" | "gt" | "ge" => &["left", "op", "right"],
            "int_add" | "fixed_add" => &["op", "result_type", "values"],
            "int_sub" | "fixed_sub" => &["left", "op", "result_type", "right"],
            "if" => &["condition", "else", "op", "result_type", "then"],
            "match_option" => &["none", "op", "result_type", "some", "subject"],
            "forall_rows" | "exists_rows" | "lookup" | "count_where" | "sum_where" => {
                return Err(type_error(TypeErrorKind::ContractOperationInRow, &op_path));
            }
            "record" | "is_some" => {
                return Err(unsupported(UnsupportedTyping::UnspecifiedForm, &op_path));
            }
            _ => return Err(type_error(TypeErrorKind::UnknownOperator, &op_path)),
        };
        let members = decode::object(value, path, keys)?;
        // 将各类运算的局部状态隔离，避免每层递归保留所有分支的栈空间。
        match op {
            "literal_bool" | "literal_text" | "literal_int" | "literal_fixed" | "literal_enum" => {
                self.infer_literal(op, members, path)
            }
            "none" | "some" | "bound" | "field" => self.infer_access(op, members, path, bindings),
            "not" | "and" | "or" => self.infer_boolean(op, members, path, bindings),
            "eq" | "lt" | "le" | "gt" | "ge" => self.infer_comparison(op, members, path, bindings),
            "int_add" | "int_sub" | "fixed_add" | "fixed_sub" => {
                self.infer_arithmetic(op, members, path, bindings)
            }
            "if" => self.infer_conditional(members, path, bindings),
            "match_option" => self.infer_match_option(members, path, bindings),
            _ => unreachable!("operator shape checked"),
        }
    }

    fn infer_literal(
        &self,
        op: &str,
        members: &decode::Members,
        path: &str,
    ) -> Result<ValueType, ExpressionError> {
        let get = |key| decode::member(members, key);
        let at = |key| decode::child(path, key);
        match op {
            "literal_bool" => {
                if !matches!(get("value"), Value::Bool(_)) {
                    return Err(type_error(TypeErrorKind::ExpectedBoolean, &at("value")));
                }
                Ok(ValueType::Bool)
            }
            "literal_text" => {
                decode::string(get("value"), &at("value"))?;
                Ok(ValueType::Text)
            }
            "literal_int" | "literal_fixed" => {
                let ty = self.annotation(get("type"), &at("type"))?;
                let (key, lower, upper) = match (&ty, op) {
                    (ValueType::Int { lower, upper }, "literal_int") => ("value", lower, upper),
                    (ValueType::Fixed { lower, upper, .. }, "literal_fixed") => {
                        ("coefficient", lower, upper)
                    }
                    (_, "literal_int") => {
                        return Err(type_error(TypeErrorKind::ExpectedInt, &at("type")));
                    }
                    _ => return Err(type_error(TypeErrorKind::ExpectedFixed, &at("type"))),
                };
                let literal = decode::integer(get(key), &at(key), false)?;
                if &literal < lower || &literal > upper {
                    return Err(type_error(TypeErrorKind::LiteralOutOfRange, &at(key)));
                }
                Ok(ty)
            }
            "literal_enum" => {
                let id = decode::id(get("enum_type"), &at("enum_type"))?;
                let index = find(self.types.enum_types(), &id).ok_or_else(|| {
                    decode::error(DeclarationErrorKind::UnresolvedReference, &at("enum_type"))
                })?;
                let member = decode::name(get("member"), &at("member"))?;
                if !self.enum_members[index].contains(member.as_str()) {
                    return Err(type_error(TypeErrorKind::UnknownEnumMember, &at("member")));
                }
                Ok(ValueType::Enum { enum_type: id })
            }
            _ => unreachable!("operator dispatched"),
        }
    }

    fn infer_access(
        &self,
        op: &str,
        members: &decode::Members,
        path: &str,
        bindings: &mut Vec<ValueType>,
    ) -> Result<ValueType, ExpressionError> {
        let get = |key| decode::member(members, key);
        let at = |key| decode::child(path, key);
        match op {
            "none" => {
                let ty = self.annotation(get("type"), &at("type"))?;
                if !matches!(ty, ValueType::Option { .. }) {
                    return Err(type_error(TypeErrorKind::ExpectedOption, &at("type")));
                }
                Ok(ty)
            }
            "some" => Ok(ValueType::Option {
                inner: Box::new(self.infer_value(get("value"), &at("value"), bindings)?),
            }),
            "bound" => {
                let index = decode::integer(get("index"), &at("index"), true)?;
                // 超过 usize 的规范数学索引必然也超过这个有限环境，归为越界而不是非法整数。
                let index = index
                    .as_str()
                    .parse::<usize>()
                    .ok()
                    .filter(|index| *index < bindings.len())
                    .ok_or_else(|| type_error(TypeErrorKind::BoundOutOfRange, &at("index")))?;
                Ok(bindings[bindings.len() - 1 - index].clone())
            }
            "field" => {
                let record = self.infer_value(get("record"), &at("record"), bindings)?;
                let ValueType::Record { record_type } = record else {
                    return Err(type_error(TypeErrorKind::ExpectedRecord, &at("record")));
                };
                let index = find(self.types.record_types(), &record_type)
                    .expect("all inferred record references resolved");
                let fields = &self.types.record_types()[index].definition().fields;
                let name = decode::name(get("field"), &at("field"))?;
                let field = fields
                    .binary_search_by(|field| field.name.as_str().cmp(&name))
                    .map_err(|_| type_error(TypeErrorKind::UnknownField, &at("field")))?;
                Ok(fields[field].value_type.clone())
            }
            _ => unreachable!("operator dispatched"),
        }
    }

    fn infer_boolean(
        &self,
        op: &str,
        members: &decode::Members,
        path: &str,
        bindings: &mut Vec<ValueType>,
    ) -> Result<ValueType, ExpressionError> {
        let get = |key| decode::member(members, key);
        let at = |key| decode::child(path, key);
        match op {
            "not" => {
                require_same(
                    &self.infer_value(get("value"), &at("value"), bindings)?,
                    &ValueType::Bool,
                    &at("value"),
                )?;
                Ok(ValueType::Bool)
            }
            "and" | "or" => {
                let values = decode::array(get("values"), &at("values"))?;
                if values.len() < 2 {
                    return Err(type_error(TypeErrorKind::WrongArity, &at("values")));
                }
                for (index, value) in values.iter().enumerate() {
                    let path = format!("{}/{}", at("values"), index);
                    require_same(
                        &self.infer_value(value, &path, bindings)?,
                        &ValueType::Bool,
                        &path,
                    )?;
                }
                Ok(ValueType::Bool)
            }
            _ => unreachable!("operator dispatched"),
        }
    }

    fn infer_comparison(
        &self,
        op: &str,
        members: &decode::Members,
        path: &str,
        bindings: &mut Vec<ValueType>,
    ) -> Result<ValueType, ExpressionError> {
        let get = |key| decode::member(members, key);
        let at = |key| decode::child(path, key);
        match op {
            "eq" | "lt" | "le" | "gt" | "ge" => {
                let left = self.infer_value(get("left"), &at("left"), bindings)?;
                let right = self.infer_value(get("right"), &at("right"), bindings)?;
                if op == "eq" {
                    require_same(&right, &left, &at("right"))?;
                    let mut ty = &left;
                    while let ValueType::Option { inner } = ty {
                        ty = inner;
                    }
                    if matches!(ty, ValueType::Record { .. }) {
                        return Err(unsupported(UnsupportedTyping::RecordEquality, path));
                    }
                } else {
                    match (&left, &right) {
                        (ValueType::Int { .. }, ValueType::Int { .. }) => {
                            if left != right {
                                return Err(unsupported(
                                    UnsupportedTyping::MixedIntComparison,
                                    path,
                                ));
                            }
                        }
                        (
                            ValueType::Fixed { scale: left, .. },
                            ValueType::Fixed { scale: right, .. },
                        ) => {
                            if left != right {
                                return Err(type_error(TypeErrorKind::ScaleMismatch, &at("right")));
                            }
                        }
                        (ValueType::Int { .. } | ValueType::Fixed { .. }, _) => {
                            return Err(type_error(TypeErrorKind::TypeMismatch, &at("right")));
                        }
                        _ => return Err(type_error(TypeErrorKind::ExpectedNumeric, &at("left"))),
                    }
                }
                Ok(ValueType::Bool)
            }
            _ => unreachable!("operator dispatched"),
        }
    }

    fn infer_arithmetic(
        &self,
        op: &str,
        members: &decode::Members,
        path: &str,
        bindings: &mut Vec<ValueType>,
    ) -> Result<ValueType, ExpressionError> {
        let get = |key| decode::member(members, key);
        let at = |key| decode::child(path, key);
        match op {
            "int_add" | "int_sub" | "fixed_add" | "fixed_sub" => {
                let (left, right, right_path) = if op.ends_with("add") {
                    let values = decode::array(get("values"), &at("values"))?;
                    if values.len() != 2 {
                        return Err(type_error(TypeErrorKind::WrongArity, &at("values")));
                    }
                    let left_path = format!("{}/0", at("values"));
                    let right_path = format!("{}/1", at("values"));
                    (
                        self.infer_value(&values[0], &left_path, bindings)?,
                        self.infer_value(&values[1], &right_path, bindings)?,
                        right_path,
                    )
                } else {
                    (
                        self.infer_value(get("left"), &at("left"), bindings)?,
                        self.infer_value(get("right"), &at("right"), bindings)?,
                        at("right"),
                    )
                };
                let result_path = at("result_type");
                let result = self.annotation(get("result_type"), &result_path)?;
                if op.starts_with("int") {
                    if !matches!(left, ValueType::Int { .. }) {
                        return Err(type_error(TypeErrorKind::ExpectedInt, path));
                    }
                    require_same(&right, &left, &right_path)?;
                    if !matches!(result, ValueType::Int { .. }) {
                        return Err(type_error(TypeErrorKind::ExpectedInt, &result_path));
                    }
                } else {
                    let ValueType::Fixed { scale, .. } = left else {
                        return Err(type_error(TypeErrorKind::ExpectedFixed, path));
                    };
                    for (ty, path) in [(&right, &right_path), (&result, &result_path)] {
                        let ValueType::Fixed { scale: other, .. } = ty else {
                            return Err(type_error(TypeErrorKind::ExpectedFixed, path));
                        };
                        if &scale != other {
                            return Err(type_error(TypeErrorKind::ScaleMismatch, path));
                        }
                    }
                }
                // 不计算算术结果，不要求输入范围等于结果范围；结果范围义务由后续阶段承担。
                Ok(result)
            }
            _ => unreachable!("operator dispatched"),
        }
    }

    fn infer_conditional(
        &self,
        members: &decode::Members,
        path: &str,
        bindings: &mut Vec<ValueType>,
    ) -> Result<ValueType, ExpressionError> {
        let get = |key| decode::member(members, key);
        let at = |key| decode::child(path, key);
        require_same(
            &self.infer_value(get("condition"), &at("condition"), bindings)?,
            &ValueType::Bool,
            &at("condition"),
        )?;
        let result = self.annotation(get("result_type"), &at("result_type"))?;
        for key in ["then", "else"] {
            require_same(
                &self.infer_value(get(key), &at(key), bindings)?,
                &result,
                &at(key),
            )?;
        }
        Ok(result)
    }

    fn infer_match_option(
        &self,
        members: &decode::Members,
        path: &str,
        bindings: &mut Vec<ValueType>,
    ) -> Result<ValueType, ExpressionError> {
        let get = |key| decode::member(members, key);
        let at = |key| decode::child(path, key);
        let subject = self.infer_value(get("subject"), &at("subject"), bindings)?;
        let ValueType::Option { inner } = subject else {
            return Err(type_error(TypeErrorKind::ExpectedOption, &at("subject")));
        };
        let result = self.annotation(get("result_type"), &at("result_type"))?;
        require_same(
            &self.infer_value(get("none"), &at("none"), bindings)?,
            &result,
            &at("none"),
        )?;
        bindings.push(*inner);
        let some = self.infer_value(get("some"), &at("some"), bindings);
        bindings.pop();
        require_same(&some?, &result, &at("some"))?;
        Ok(result)
    }
}

fn find<T>(entries: &[NormalizedDeclaration<T>], id: &str) -> Option<usize> {
    entries.binary_search_by(|entry| entry.id().cmp(id)).ok()
}

fn require_same(
    actual: &ValueType,
    expected: &ValueType,
    path: &str,
) -> Result<(), ExpressionError> {
    if actual == expected {
        Ok(())
    } else {
        Err(type_error(TypeErrorKind::TypeMismatch, path))
    }
}

fn type_error(kind: TypeErrorKind, path: &str) -> ExpressionError {
    ExpressionError::Type {
        kind,
        path: path.to_owned(),
    }
}

fn unsupported(reason: UnsupportedTyping, path: &str) -> ExpressionError {
    ExpressionError::Unsupported {
        reason,
        path: path.to_owned(),
    }
}

#[cfg(test)]
mod corpus_tests {
    use super::*;
    use crate::normalization::normalize_type_declarations;
    use std::collections::BTreeMap;

    // 只为读取既有 fixture 组装测试环境，不作为生产节点解析或图验收路径。
    fn get<'a>(value: &'a Value, key: &str) -> &'a Value {
        let Value::Object(members) = value else {
            panic!("fixture object")
        };
        decode::member(members, key)
    }

    fn text(value: &Value) -> &str {
        decode::string(value, "").unwrap()
    }
    fn array(value: &Value) -> &[Value] {
        decode::array(value, "").unwrap()
    }

    #[test]
    fn all_31_row_expressions_in_the_twelve_candidates_match_declared_output_types() {
        let cases = [
            ("ax-b01", "correct", 3),
            ("ax-b01", "wrong-add", 3),
            ("ax-b01", "wrong-drop-zero", 3),
            ("ax-b02", "correct", 2),
            ("ax-b02", "wrong-constant-tier", 2),
            ("ax-b02", "wrong-region-join", 2),
            ("ax-b03", "correct", 0),
            ("ax-b03", "wrong-single-group", 3),
            ("ax-b03", "wrong-unit-sum", 3),
            ("ax-b04", "correct", 3),
            ("ax-b04", "wrong-sensitive-filter", 4),
            ("ax-b04", "wrong-sensitive-priority", 3),
        ];
        let root = std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
            .join("../../benchmarks/keyed-finite-table-v0.1");
        let limits = JsonLimits {
            max_input_bytes: 1024 * 1024,
            max_values: 100_000,
            max_nesting: 128,
        };
        let mut total = 0;
        for (task, candidate, expected_count) in cases {
            let bytes = std::fs::read(
                root.join(task)
                    .join("candidates")
                    .join(format!("{candidate}.ir.json")),
            )
            .unwrap();
            let types = normalize_type_declarations(&bytes, limits).unwrap();
            let checker = RowTypeChecker::new(&types);
            let document = json::parse(&bytes, limits).unwrap();
            let nodes: BTreeMap<_, _> = array(get(&document, "nodes"))
                .iter()
                .map(|node| (text(get(node, "id")), get(node, "definition")))
                .collect();
            let table_records: BTreeMap<_, _> = types
                .table_types()
                .iter()
                .map(|table| (table.id(), table.definition().record_type.as_str()))
                .collect();
            let node_record = |node: &Value| table_records[text(get(node, "table_type"))];
            let mut count = 0;
            for node in nodes.values() {
                let kind = text(get(node, "kind"));
                if kind == "input" || kind == "group" {
                    continue;
                }
                let scope = match kind {
                    "filter" | "map" => RowScope::Single {
                        record_type: node_record(nodes[text(get(node, "source"))]),
                    },
                    "lookup_join" => RowScope::Join {
                        left_record_type: node_record(nodes[text(get(node, "left"))]),
                        right_record_type: node_record(nodes[text(get(node, "right"))]),
                    },
                    _ => panic!("unexpected fixture node"),
                };
                let check = |expression: &Value, expected: &ValueType| {
                    let mut bytes = Vec::new();
                    json::encode(expression, &mut bytes);
                    assert_eq!(
                        &checker.infer(&bytes, limits, scope).unwrap(),
                        expected,
                        "{task}/{candidate}"
                    );
                };
                if kind == "filter" {
                    check(get(node, "predicate"), &ValueType::Bool);
                    count += 1;
                } else {
                    let record = &types.record_types()
                        [find(types.record_types(), node_record(node)).unwrap()];
                    for projection in array(get(node, "fields")) {
                        let name = text(get(projection, "name"));
                        // 期望直接来自 fixture 的输出字段声明，不由表达式推导器生成。
                        let expected = &record
                            .definition()
                            .fields
                            .iter()
                            .find(|field| field.name == name)
                            .unwrap()
                            .value_type;
                        check(get(projection, "expression"), expected);
                        count += 1;
                    }
                }
            }
            assert_eq!(count, expected_count, "{task}/{candidate}");
            total += count;
        }
        assert_eq!(total, 31);
    }
}
