//! v0.2 的闭合记录构造；所有字段共享外层环境，不引入字段名或行绑定。

use super::*;

impl RowTypeChecker<'_> {
    pub(super) fn infer_record(
        &self,
        members: &decode::Members,
        path: &str,
        context: &mut TypingContext<'_>,
    ) -> Result<ValueType, ExpressionError> {
        let record_path = decode::child(path, "record_type");
        let record_type = decode::id(decode::member(members, "record_type"), &record_path)?;
        let record = find(self.types.record_types(), &record_type).ok_or_else(|| {
            decode::error(DeclarationErrorKind::UnresolvedReference, &record_path)
        })?;
        let declared = &self.types.record_types()[record].definition().fields;
        let fields_path = decode::child(path, "fields");
        let fields = decode::array(decode::member(members, "fields"), &fields_path)?;
        let mut seen = BTreeSet::new();
        for (index, field) in fields.iter().enumerate() {
            let path = format!("{fields_path}/{index}");
            let members = decode::object(field, &path, &["expression", "name"])?;
            let name_path = decode::child(&path, "name");
            let name = decode::name(decode::member(members, "name"), &name_path)?;
            let index = declared
                .binary_search_by(|field| field.name.cmp(&name))
                .map_err(|_| type_error(TypeErrorKind::UnknownField, &name_path))?;
            if !seen.insert(name) {
                return Err(decode::error(DeclarationErrorKind::DuplicateName, &name_path).into());
            }
            let expression_path = decode::child(&path, "expression");
            let actual = self.infer_value(
                decode::member(members, "expression"),
                &expression_path,
                context,
            )?;
            require_same(&actual, &declared[index].value_type, &expression_path)?;
        }
        if seen.len() != declared.len() {
            return Err(type_error(TypeErrorKind::IncompleteFields, &fields_path));
        }
        Ok(ValueType::Record { record_type })
    }
}
