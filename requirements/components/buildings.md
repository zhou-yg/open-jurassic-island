# Buildings

at config/buildings.gd

> [!NOTE]
> All numeric values (cost, build time, HP, damage, upgrade levels, ...) live in
> `config/buildings.gd` (`class_name BuildingsConfig`) and
> `config/resources.gd` (`class_name ResourcesConfig`).
> This document describes the design intent; the config is the source of truth.

buildings of survival game 

## basic 

- camp
  - props:
    - heal point = 5
  - description:
    - heal HP
- campfire
  - props:
    - heal point = 1
  - description:
    - heal MP

## monkey worker

- description:
  - need food to work
  - stop work when is scared

- wood monkey
  - description:
    - collect wood from tree
    - move to camp

- stone monkey
  - description:
    - collect stone from big stone
    - move to camp

## food (banana)

this is a resource provide to food-costed buildings

- banana factory
  - description:
    - hang on banana-tree
    - must place at least 10m away from other banana-tree
    - supporting upgrade levels


## guard

- wooden wall
  - description:
    - cost time and resources can be upgraded to stone wall

- stone wall

- wooden gate
  - description:
    - can be upgraded to stone gate
    - 2 states: open / close

- stone gate

## defense

### pre-tech

- defense college
  - props:
    - cost time = 120s
    - cost resources
      - wood = 100
      - stone = 100
      - food = 1
        - description:
          - old professor monkey for teaching monkey
  - description:
    - enable or upgrade to defense college level.1/2/3

### monkey turret series

fast speed low damage

- monkey turret level.1
- monkey turret level.2
- monkey turret level.3

### monkey mangonel series

slow speed high damage

- monkey mangonel level.1
- monkey mangonel level.2
- monkey mangonel level.3

## army

### pre-tech point

- army college
  - props:
    - cost time = 120s
    - cost resources
      - wood = 100
      - stone = 100
      - food = 1
        - description:
          - old solider monkey for teaching monkey
  - description:
    - enable or upgrade to monkey army

### army equipments series

- armor
- gun
- RPG

## vehicle

### pre-tech point

- vehicle college
  - props:
    - cost time = 120s
    - cost resources
      - wood = 100
      - stone = 100
      - food = 1
        - description:
          - old solider monkey for teaching monkey
  - description:
    - enable or upgrade to vehicle

### vehicle series

- strong monkey (auto enabled at initial)
- wood vehicle
- stone vehicle

# resources

at config/resources.gd

- wood
- stone