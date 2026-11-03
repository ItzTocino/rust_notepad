use std::{any::type_name, io, str::FromStr};

#[derive(Debug)]
pub enum RetrievalError {
    StdError,
    UnparseableError,
}

pub struct Input;

impl Input {
    pub fn parse<T: FromStr>(value: String) -> Result<T, <T as FromStr>::Err> {
        value.parse::<T>()
    }

    pub fn retrieve<T: FromStr>() -> Result<T, RetrievalError> {
        let mut buffer = String::new();
        io::stdin()
            .read_line(&mut buffer)
            .map_err(|_| RetrievalError::StdError)?;
        Self::parse(buffer.trim().to_owned()).map_err(|_| RetrievalError::UnparseableError)
    }

    pub fn request<T: FromStr>(message: Option<String>, retries: Option<usize>) -> Option<T> {
        let output = message.unwrap_or_else(|| format!("Please enter a {}.", type_name::<T>()));
        eprintln!("{output}");

        for _ in 0..retries.unwrap_or(5) {
            if let Ok(result) = Self::retrieve::<T>() {
                return Some(result);
            }
        }

        None
    }
}

#[cfg(test)]
mod tests {
    use super::Input;

    #[test]
    fn parses_a_valid_value() {
        assert_eq!(Input::parse::<i32>("42".to_owned()), Ok(42));
    }

    #[test]
    fn rejects_an_invalid_value() {
        assert!(Input::parse::<i32>("not a number".to_owned()).is_err());
    }
}
