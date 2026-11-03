use iced::{Element, widget::text};

fn view(_: &()) -> Element<'_, ()> {
    text("Welcome!").into()
}

fn update(_: &mut (), _: ()) {}

fn main() -> iced::Result {
    iced::application("Ellie's Notepad", update, view).run()
}
