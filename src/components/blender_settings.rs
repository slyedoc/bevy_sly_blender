mod lighting;

use bevy::prelude::*;

pub(crate) fn plugin(app: &mut App) {
    app.add_plugins(lighting::plugin);
}
