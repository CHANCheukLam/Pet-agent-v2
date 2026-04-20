# AGENTS.md

## Scope

Use the following JSON files as the source of truth for pet-transport decisions:

- `pet_urban_transit_rules_beijing_shanghai_v1.json`
- `pet_air_transport_rules_cn_jinghu_compact_v1.json`
- `pet_rail_transport_rules_cn_hsr_v1.json`

## Operating Principles

- MUST follow the strictest applicable rule when multiple rules overlap.
- MUST NOT assume pets are allowed unless the relevant JSON explicitly allows them.
- MUST ask for clarification when city, mode, airline, animal type, or required documents are missing.
- MUST keep urban transit, airline, and rail rules separate unless the user explicitly combines them.
- MUST NOT invent exceptions, documents, limits, or routes that are not in the JSON.

---

## Transport Rules

### 1) Urban Transit: Beijing and Shanghai

#### Beijing Metro / Light Rail
- MUST NOT carry pets or animals, including cats and dogs. (source: `pet_urban_transit_rules_beijing_shanghai_v1.json`)
- ONLY explicit working-animal exceptions may be considered.
- Allowed exceptions in the source:
  - guide dogs
  - police dogs
- MUST treat all other animals as prohibited, including birds, livestock, poultry, wild animals, and any animal that may affect transit safety or passenger order.

#### Beijing Bus
- MUST NOT carry pets or animals.
- ONLY guide dogs in working state may be carried.
- MUST require all of the following for the exception:
  - disability certificate
  - guide dog work certificate
  - animal health immunization proof
- MUST require the guide dog to be leashed, wear a guide harness, and remain in working state.

#### Shanghai Metro / Tram
- MUST NOT carry live poultry or animals such as cats and dogs.
- ONLY explicit working-animal exceptions may be considered.
- Allowed exceptions in the source:
  - guide dogs
  - military dogs
  - police dogs
- MUST treat all other animals as prohibited.

#### Shanghai Bus
- MUST NOT carry live poultry, cats, dogs, or any other animals.
- ONLY explicit working-animal exceptions may be considered.
- Allowed exceptions in the source:
  - guide dogs
  - military dogs
  - police dogs
- MUST require the animal to be in working state and not disrupt the bus environment.

---

### 2) Airline Rules: Beijing-Shanghai Domestic Corridor

#### Scope
- ONLY use these airline rules for domestic Beijing-Shanghai corridor travel.
- Supported airport scope in the source:
  - Beijing: PEK, PKX
  - Shanghai: PVG, SHA (source: `pet_air_transport_rules_cn_jinghu_compact_v1.json`)

#### Global Baseline
- MUST treat cats and dogs as the primary pet types in scope.
- MUST apply the default max pet-plus-kennel weight limit of 32 kg unless a service-specific rule is stricter.
- MUST treat the default check-in window as 120 minutes before departure unless the airline rule is stricter.
- SHOULD require:
  - Animal Quarantine Certificate
  - Vaccination proof, especially for dogs
- MUST treat the following as common restrictions:
  - snub-nosed breeds may be restricted
  - aggressive or dangerous breeds may be restricted
  - pregnant / just-postpartum pets may be restricted
  - very young pets are restricted by airline-specific minimum age
  - pets not fit for flight can be denied

#### MU / FM: China Eastern / Shanghai Airlines
**Checked cargo**
- MUST require direct MU/FM-operated flights only.
- MUST accept requests only in the domestic booking window of T-7d to T-48h.
- MUST NOT exceed 2 pets per passenger.
- MUST NOT exceed 32 kg pet-plus-kennel weight.
- MUST require pet age of at least 6 months.
- MUST treat temperature outside the recommended range as a risk warning:
  - at or below -12°C
  - at or above 30°C
- MUST require kennel compliance:
  - IATA-sized kennel
  - one pet per kennel
  - metal lockable door
  - at least 3-side ventilation
  - absorbent pad
  - nylon tie + net + strapping reinforcement

**In-cabin**
- MUST require request submission up to T-24h.
- MUST NOT exceed 1 pet per passenger.
- MUST NOT exceed 2 pets per flight.
- ONLY the seat option is allowed when explicitly selected.
- Seat-option kennel MUST NOT exceed 55 × 35 × 35 cm.
- Seat-option pet-plus-kennel weight MUST NOT exceed 18 kg.
- MUST require:
  - adult handler
  - muzzle
  - diaper
  - no odor or noise disturbance

#### CA: Air China
**Checked cargo**
- MUST require CA-operated flights with CA flight number.
- MUST require a domestic request deadline of T-2h.
- MUST NOT exceed 1 pet per passenger.
- MUST NOT exceed 32 kg pet-plus-kennel weight.
- MUST require pet age of at least 8 weeks.
- MUST require oxygen-capable hold.
- MUST NOT accept unsupported aircraft models:
  - A319
  - A320
  - 737-8MAX
  - ARJ21-700
- MUST require kennel compliance:
  - IATA-sized kennel
  - secure metal door
  - metal-mesh protected openings
  - leakproof floor + absorbent pad
  - fixed water/food setup

**In-cabin**
- MUST treat standard paid pet-in-cabin service as unavailable in this scope.

#### CZ: China Southern
**Checked cargo**
- MUST require domestic direct flights only.
- MUST require a booking deadline of T-4h.
- MUST NOT exceed 32 kg pet-plus-kennel weight.
- MUST require pet age of at least 8 weeks.
- MUST treat temperature outside the recommended range as a risk warning:
  - outside -12°C to 30°C
- MUST require kennel dimensions within:
  - minimum 5 × 15 × 20 cm
  - maximum 90 × 60 × 66 cm

**In-cabin**
- MUST allow only small cats and small dogs.
- MUST NOT exceed 1 pet per passenger.
- MUST NOT exceed 4 pets per flight.
- MUST treat C909 as excluded.
- MUST require:
  - app or mini-program request channel
  - quarantine certificate
  - vaccination proof
  - arrival at least 120 minutes before departure

#### HU: Hainan Airlines
**Checked cargo**
- MUST require a booking window before T-24h.
- MUST allow only domestic HU self-operated flights.
- MUST NOT support transfer through-check.
- MUST NOT exceed 32 kg pet-plus-kennel weight.
- MUST NOT exceed 2 pets per passenger.
- MUST require pet age of at least 8 weeks.
- MUST NOT accept the following aircraft:
  - A320NEO
  - A321NEO
- MUST treat temperature at or below -12°C or at or above 30°C at any route point as a hard stop.

**In-cabin**
- MUST allow economy class only.
- MUST NOT support transfer itineraries.
- MUST NOT exceed 2 pets per passenger.
- MUST apply the two-pet mode rule:
  - one occupied-seat pet
  - one non-seat pet
- MUST respect per-flight limits:
  - narrow-body: 4
  - wide-body: 6
- MUST require kennel sizes within:
  - non-seat: 35 × 28 × 24 cm
  - seat: 55 × 28 × 24 cm
- MUST support these booking windows:
  - app / msite / mini-program: T-7d to T-48h
  - hotline / ticket office: T-7d to T-24h
  - airport walk-in: within T-24h and at least 120 minutes before departure, with rejection risk
- MUST require:
  - Animal Quarantine Certificate
  - vaccination proof for dogs
  - signed cabin pet transport agreement

---

### 3) Rail Rules: China High-Speed Rail

#### Eligibility
- MUST allow only healthy household cats and dogs.
- MUST NOT allow:
  - aggressive dogs, including fierce breeds
  - sick pets
  - pregnant pets
  - juvenile pets
  - wild beasts or raptors
  - attack-prone animals
  - snakes
  - scorpions
  - centipedes
  - bees

#### Size / Weight Limits
- MUST NOT exceed 33.1 lb pet weight.
- MUST NOT exceed 40 cm shoulder height.
- MUST NOT exceed 52 cm body length.
- MUST NOT exceed 44.1 lb total container weight.

#### Container Requirements
- MUST use a container that is:
  - ventilated
  - sturdy / firm
  - equipped with a secure locking mechanism
  - equipped with a water dispenser
  - lined to prevent feces leakage
- MUST treat a non-compliant container as a hard stop.

#### Documents
- MUST require:
  - valid sender ID
  - valid Animal Quarantine Certificate
- MUST require the receiver to present required credentials at the destination station business office for pickup.

#### Booking / Station Flow
- MUST support the Beijing Government workflow variant:
  - book online via CRE WeChat mini-program 2–5 days in advance
  - submit pet information
  - bring ID, quarantine certificate, and compliant container to the designated HSR station CRE office
  - complete on-site consignment
  - receiver picks up at destination station office
- MUST support the CCTV workflow variant:
  - arrive at the station consignment window at least 4 hours before departure
  - bring sender ID and valid quarantine certificate
  - complete baggage-car pet consignment and escort formalities
- WHEN workflow is unclear, MUST prefer the stricter / earlier time requirement.

---

## Hard Constraints

### Urban Transit
- MUST deny by default on Beijing and Shanghai urban transit.
- MUST allow only explicit working-animal exceptions.
- MUST NOT generalize one city’s exception to another city’s mode.
- MUST NOT carry cats, dogs, birds, livestock, poultry, or other animals unless the source explicitly allows the exception.

### Airline
- MUST deny if route, airline, aircraft, time window, age, weight, or kennel limits are not satisfied.
- MUST deny if the required docs are missing.
- MUST deny if the pet is restricted, unfit for flight, or outside the airline’s minimum age rule.
- MUST apply the stricter rule whenever the global baseline and airline-specific rule differ.

### Rail
- MUST deny if the pet exceeds weight, height, length, or container limits.
- MUST deny if the pet is in a prohibited category.
- MUST deny if the quarantine certificate is missing or invalid.
- MUST deny if the chosen workflow timing is not satisfied.

---

## Edge Cases / Special Conditions

### Urban Transit
- Beijing bus is the strictest exception case: only a working guide dog is allowed, with required documents.
- Beijing metro / light rail allow guide dogs and police dogs only.
- Shanghai metro / tram allow guide dogs, military dogs, and police dogs only.
- Shanghai bus follows the same explicit working-animal exception logic as the city rules in the source.
- If the user says “pet” without specifying working-animal status, MUST treat it as prohibited unless clarified.

### Airline
- MU/FM cargo:
  - direct flights only
  - in-cabin seat option has a separate size/weight limit
- CA cargo:
  - specific aircraft models are not supported
  - no standard paid in-cabin service in the provided scope
- CZ in-cabin:
  - C909 excluded
  - only small cats and small dogs
- HU in-cabin:
  - economy only
  - no transfer itineraries
  - two-pet mode is special: one occupied-seat + one non-seat
- Temperature rules are not uniform:
  - some are warnings
  - HU checked cargo is a hard stop at the temperature threshold

### Rail
- Two booking workflows exist in the source; do not collapse them into a single time window unless the user asks for a simplified policy.
- If the source or station workflow is unclear, ask for clarification or use the stricter timing.
- The source is focused on healthy household cats and dogs; all other animals are excluded.

---

## Fallback Rules

- IF a required field is missing, MUST ask for it or return an explicit missing-input status.
- IF the user request is ambiguous, MUST ask a clarifying question instead of guessing.
- IF multiple rules apply, MUST use the strictest applicable rule.
- IF a city or mode is outside the known scope, MUST NOT infer permission.
- IF a service is not explicitly available in the source, MUST treat it as unavailable.
- IF the agent must explain a decision, it SHOULD cite the relevant rule source in plain language.

