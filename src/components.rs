use crate::{ronstring_to_reflect_component, GltfBlueprintsSet};
use bevy::{
    ecs::{reflect::ReflectComponent, world::World},
    gltf::GltfExtras,
    prelude::*,
    reflect::{Reflect, TypeRegistration},
    utils::HashMap,
};

pub fn plugin(app: &mut App) {
    app
        // rest
        .add_systems(
            Update,
            (add_components_from_gltf_extras).in_set(GltfBlueprintsSet::Injection),
        );
}

pub fn add_components_from_gltf_extras(world: &mut World) {
    let mut extras =
        world.query_filtered::<(Entity, &GltfExtras), Changed<GltfExtras>>();
    let mut entity_components: HashMap<Entity, Vec<(Box<dyn Reflect>, TypeRegistration)>> =
        HashMap::new();

    for (entity, extra) in extras.iter(world) {
        //info!("proccess extra: {:?} {:?}", entity, name);

        let type_registry: &AppTypeRegistry = world.resource();
        let type_registry = type_registry.read();
        let reflect_components = ronstring_to_reflect_component(&extra.value, &type_registry);

        // if there where already components set to be added to this entity (for example when entity_data was refering to a parent), update the vec of entity_components accordingly
        // this allows for example blender collection to provide basic ecs data & the instances to override/ define their own values
        if entity_components.contains_key(&entity) {
            let mut updated_components: Vec<(Box<dyn Reflect>, TypeRegistration)> = Vec::new();
            let current_components = &entity_components[&entity];
            // first inject the current components
            for (component, type_registration) in current_components {
                updated_components.push((component.clone_value(), type_registration.clone()));
            }
            // then inject the new components: this also enables overwrite components set in the collection
            for (component, type_registration) in reflect_components {
                updated_components.push((component.clone_value(), type_registration));
            }
            entity_components.insert(entity, updated_components);
        } else {
            entity_components.insert(entity, reflect_components);
        }
    }

    for (entity, components) in entity_components {
        let type_registry: &AppTypeRegistry = world.resource();
        let type_registry = type_registry.clone();
        let type_registry = type_registry.read();

        //if !components.is_empty() {
        //     debug!("--entity {:?}, components {}", entity, components.len());
        //}
        for (component, type_registration) in components {
            // debug!(
            //     "------adding {} {:?}",
            //     component.get_represented_type_info().unwrap().type_path(),
            //     component
            // );
            let mut entity_mut = world.entity_mut(entity);
            type_registration
                .data::<ReflectComponent>()
                .expect("Unable to reflect component")
                .insert(&mut entity_mut, &*component, &type_registry);
        }
    }
}
