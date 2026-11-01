//! Bounded canonical ASCII JSON for the private report, not a general parser.
#[derive(Clone, Debug, Eq, PartialEq)]
pub(crate) enum J {
    N,
    B(bool),
    U(u64),
    S(String),
    A(Vec<J>),
    O(Vec<(String, J)>),
}
pub(crate) type R<T> = Result<T, &'static str>;
pub(crate) fn obj(items: impl IntoIterator<Item = (&'static str, J)>) -> J {
    J::O(items.into_iter().map(|(k, v)| (k.into(), v)).collect())
}
pub(crate) fn s(v: impl Into<String>) -> J {
    J::S(v.into())
}
impl J {
    pub(crate) fn fields(&self, keys: &[&str]) -> R<&[(String, J)]> {
        let J::O(v) = self else { return Err("object") };
        if v.len() != keys.len() || v.iter().zip(keys).any(|((k, _), e)| k != e) {
            return Err("fields");
        };
        Ok(v)
    }
    pub(crate) fn u(&self) -> R<u64> {
        if let J::U(v) = self {
            Ok(*v)
        } else {
            Err("integer")
        }
    }
    pub(crate) fn b(&self) -> R<bool> {
        if let J::B(v) = self {
            Ok(*v)
        } else {
            Err("boolean")
        }
    }
    pub(crate) fn text(&self) -> R<&str> {
        if let J::S(v) = self {
            Ok(v)
        } else {
            Err("string")
        }
    }
    pub(crate) fn array(&self) -> R<&[J]> {
        if let J::A(v) = self {
            Ok(v)
        } else {
            Err("array")
        }
    }
    pub(crate) fn bytes(&self) -> Vec<u8> {
        fn out(j: &J, b: &mut Vec<u8>) {
            match j {
                J::N => b.extend_from_slice(b"null"),
                J::B(v) => b.extend_from_slice(if *v { b"true" } else { b"false" }),
                J::U(v) => b.extend_from_slice(v.to_string().as_bytes()),
                J::S(v) => {
                    b.push(b'"');
                    b.extend_from_slice(v.as_bytes());
                    b.push(b'"')
                }
                J::A(v) => {
                    b.push(b'[');
                    for (i, j) in v.iter().enumerate() {
                        if i > 0 {
                            b.push(b',')
                        }
                        out(j, b)
                    }
                    b.push(b']')
                }
                J::O(v) => {
                    b.push(b'{');
                    for (i, (k, j)) in v.iter().enumerate() {
                        if i > 0 {
                            b.push(b',')
                        }
                        out(&J::S(k.clone()), b);
                        b.push(b':');
                        out(j, b)
                    }
                    b.push(b'}')
                }
            }
        }
        let mut b = Vec::new();
        out(self, &mut b);
        b
    }
}
pub(crate) fn parse(raw: &[u8]) -> R<J> {
    struct P<'a> {
        b: &'a [u8],
        p: usize,
    }
    impl P<'_> {
        fn take(&mut self, c: u8) -> R<()> {
            if self.b.get(self.p) != Some(&c) {
                return Err("json-token");
            }
            self.p += 1;
            Ok(())
        }
        fn string(&mut self) -> R<String> {
            self.take(b'"')?;
            let start = self.p;
            while let Some(&c) = self.b.get(self.p) {
                if c == b'"' {
                    let v = std::str::from_utf8(&self.b[start..self.p])
                        .map_err(|_| "ascii")?
                        .to_string();
                    self.p += 1;
                    return Ok(v);
                }
                if !(32..=126).contains(&c) || c == b'\\' || self.p - start >= 256 {
                    return Err("json-string");
                };
                self.p += 1
            }
            Err("json-truncated")
        }
        fn value(&mut self, d: usize) -> R<J> {
            if d > 16 {
                return Err("json-depth");
            };
            match self.b.get(self.p) {
                Some(b'"') => Ok(J::S(self.string()?)),
                Some(b'0'..=b'9') => {
                    let start = self.p;
                    while self.b.get(self.p).is_some_and(u8::is_ascii_digit) {
                        self.p += 1
                    }
                    let b = &self.b[start..self.p];
                    if b.len() > 1 && b[0] == b'0' {
                        return Err("json-number");
                    }
                    Ok(J::U(
                        std::str::from_utf8(b)
                            .map_err(|_| "integer")?
                            .parse()
                            .map_err(|_| "integer")?,
                    ))
                }
                Some(b'[') => {
                    self.p += 1;
                    let mut v = Vec::new();
                    if self.b.get(self.p) != Some(&b']') {
                        loop {
                            if v.len() == 64 {
                                return Err("json-array");
                            };
                            v.push(self.value(d + 1)?);
                            if self.b.get(self.p) != Some(&b',') {
                                break;
                            }
                            self.p += 1;
                        }
                    }
                    self.take(b']')?;
                    Ok(J::A(v))
                }
                Some(b'{') => {
                    self.p += 1;
                    let mut v: Vec<(String, J)> = Vec::new();
                    if self.b.get(self.p) != Some(&b'}') {
                        loop {
                            if v.len() == 32 {
                                return Err("json-object");
                            };
                            let k = self.string()?;
                            if v.iter().any(|(a, _)| a == &k) {
                                return Err("json-duplicate");
                            };
                            self.take(b':')?;
                            v.push((k, self.value(d + 1)?));
                            if self.b.get(self.p) != Some(&b',') {
                                break;
                            }
                            self.p += 1;
                        }
                    }
                    self.take(b'}')?;
                    Ok(J::O(v))
                }
                _ => {
                    for (lit, j) in [
                        (b"null".as_slice(), J::N),
                        (b"true".as_slice(), J::B(true)),
                        (b"false".as_slice(), J::B(false)),
                    ] {
                        if self.b.get(self.p..self.p + lit.len()) == Some(lit) {
                            self.p += lit.len();
                            return Ok(j);
                        }
                    }
                    Err("json-value")
                }
            }
        }
    }
    if raw.len() > 32768 {
        return Err("json-size");
    };
    let mut p = P { b: raw, p: 0 };
    let j = p.value(0)?;
    if p.p != raw.len() || j.bytes() != raw {
        return Err("json-canonical");
    };
    Ok(j)
}
