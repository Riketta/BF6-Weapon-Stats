import argparse
import math
import csv
import matplotlib.pyplot as plt
from enum import StrEnum
from itertools import cycle
from typing import Any, Optional

STATS_FILE = "Stats.csv"
RANGES = {
    "0 m": 0,
    "10 m": 10,
    # "15 m": 15,  # Same as previous.
    "20 m": 20,
    # "25 m": 25,  # Same as previous.
    # "35 m": 35,  # Same as previous.
    "40 m": 40,
    # "50 m": 50,  # Same as previous.
    # "55 m": 55,  # Same as previous.
    # "70 m": 70,  # Same as previous.
    "70+ m": 70,
}


class WeaponClass(StrEnum):
    All = "All"
    Specific = "Specific"
    AR = "AR"
    Carbine = "Carbine"
    SMG = "SMG"
    LMG = "LMG"
    DMR = "DMR"
    Pistol = "Pistol"


class DamageProfileType(StrEnum):
    Body = "Body"
    SingleMissAndBody = "1Miss"
    SingleHeadshotsAndBody = "1HS"


class HealthProfileType(StrEnum):
    Multiplayer = "MP"
    Gauntlet = "Gauntlet"
    BattleRoyale = "BR"


class HealthProfile:
    def __init__(
        self,
        name: str,
        health: int,
        plates: int,
        plate_health: int,
        plate_damage_reduction: float,
    ):
        self.name = name

        self.health = health
        self.plates = plates
        self.plate_health = plate_health
        self.plate_damage_reduction = plate_damage_reduction


HEALTH_PROFILES = {
    HealthProfileType.Multiplayer: HealthProfile(
        HealthProfileType.Multiplayer, 100, 0, 0, 0
    ),
    HealthProfileType.Gauntlet: HealthProfile(
        HealthProfileType.Gauntlet, 100, 1, 40, 0
    ),
    HealthProfileType.BattleRoyale: HealthProfile(
        HealthProfileType.BattleRoyale, 100, 2, 40, 0.2
    ),
}


class FalloffDamage:
    def __init__(self, damage: float, range: int, range_tag: str):
        self.damage = damage
        self.range = range
        self.range_tag = range_tag


class Weapon:
    def __init__(self, row: dict[str, Any]):
        self.name: str = row["Weapon"]
        self.weapon_class: WeaponClass = row["Class"]
        self.headshot_multiplier: float = float(row["HS Mult"])
        self.rpm: int = int(row["RPM"])
        self.shot_intverval: int = int(60_000 / self.rpm)

        self.damage_falloffs: list[FalloffDamage] = []
        for range_tag, range in RANGES.items():
            self.damage_falloffs.append(
                FalloffDamage(float(row[range_tag]), range, range_tag)
            )

        last_damage_falloff = self.damage_falloffs[-1]
        self.damage_falloffs.append(
            FalloffDamage(
                last_damage_falloff.damage, int(last_damage_falloff.range + 15), ""
            )
        )


class DamageProfile:
    def __init__(
        self,
        name: str,
        headshots: int,
        headshot_multiplier_override: Optional[float] = None,
        misses: int = 0,
    ):
        self.name = name

        self.headshots = headshots
        self.headshot_multiplier_override = headshot_multiplier_override
        self.misses = misses


DAMAGE_PROFILES = {
    DamageProfileType.SingleHeadshotsAndBody: DamageProfile("1 Headshot", 1),
    DamageProfileType.Body: DamageProfile("All Body", 0),
    DamageProfileType.SingleMissAndBody: DamageProfile(
        "All Body + 1 Miss", 0, misses=1
    ),
}


class WeaponRangeDamageStats:
    def __init__(
        self,
        ttk: int,
        shots: int,
        range: int,
    ):
        self.TTK = ttk
        self.Shots = shots
        self.Range = range


class Preset:
    def __init__(
        self,
        name: str,
        health_profile: HealthProfile,
        damage_profile: DamageProfile,
        weapon_class: WeaponClass = WeaponClass.All,
    ):
        self.name = name
        self.health_profile = health_profile
        self.damage_profile = damage_profile
        self.weapon_class = weapon_class

    def calc_ttk(self, weapon: Weapon):
        headshot_multiplier = (
            self.damage_profile.headshot_multiplier_override
            or weapon.headshot_multiplier
        )

        weapon_damage_stats_per_range: list[WeaponRangeDamageStats] = []
        for falloff_damage in weapon.damage_falloffs:
            damage = falloff_damage.damage
            headshot_damage = damage * headshot_multiplier

            total_health = self.health_profile.health
            total_shots = self.damage_profile.misses

            # Calculate plate damage.
            # TODO: somewhat accurate but tune it in future.
            scale = 100
            plate_dr_scaled = self.health_profile.plate_damage_reduction * scale
            effective_plate_health = (
                self.health_profile.plate_health * scale / (scale - plate_dr_scaled)
            )
            total_health += effective_plate_health * self.health_profile.plates

            # Calculate headshots.
            total_shots += self.damage_profile.headshots
            remaining_health = total_health - (
                self.damage_profile.headshots * headshot_damage
            )

            # Calculate body shots.
            body_shots = math.ceil(remaining_health / damage)
            total_shots += body_shots

            # First shot happens instantly so have to exclude it.
            ttk: int = (total_shots - 1) * weapon.shot_intverval

            range_damage_stats = WeaponRangeDamageStats(
                ttk, total_shots, falloff_damage.range
            )
            weapon_damage_stats_per_range.append(range_damage_stats)

        return weapon_damage_stats_per_range

    def description(self):
        health_profile = [
            "{health} HP".format(health=self.health_profile.health),
        ]
        if self.health_profile.plates > 0:
            health_profile.append(
                "{plates} Plate(s)".format(plates=self.health_profile.plates)
            )
        if self.health_profile.plate_damage_reduction > 0:
            health_profile.append(
                "{plate_damage_reduction}% Plate DR".format(
                    plate_damage_reduction=self.health_profile.plate_damage_reduction
                    * 100
                )
            )

        description = (
            "{health_profile_name} ({health_profile}), {damage_profile}".format(
                health_profile_name=self.health_profile.name,
                health_profile=", ".join(health_profile),
                damage_profile=self.damage_profile.name,
            )
        )

        return description


def read_weapon_stats():
    weapons: list[Weapon] = []
    with open(STATS_FILE) as csvfile:
        weapon_stats_reader = csv.DictReader(csvfile)
        for row in weapon_stats_reader:
            # print(row)
            weapon = Weapon(row)
            weapons.append(weapon)
    return weapons


class PlotType(StrEnum):
    TTK = "TTK"
    Shots = "Shots"


def plot(
    weapons: list[Weapon],
    preset: Preset,
    plot_type: PlotType = PlotType.TTK,
    fixed_ticks: Optional[range] = None,
    evenly_spaces_ranges: bool = False,
    show: bool = True,
):
    plt.figure(figsize=(10, 6))
    line_styles = cycle([":", "-."])
    for weapon in weapons:
        weapon_damage_stats_per_range = preset.calc_ttk(weapon)
        y = None
        match plot_type:
            case PlotType.TTK:
                y = list(map(lambda value: value.TTK, weapon_damage_stats_per_range))
            case PlotType.Shots:
                y = list(map(lambda value: value.Shots, weapon_damage_stats_per_range))
        x = (
            list(range(len(y)))
            if evenly_spaces_ranges
            else list(map(lambda value: value.Range, weapon_damage_stats_per_range))
        )

        # plt.plot(x, y, marker="o", label=weapon.name)
        plt.step(
            x,
            y,
            where="post",
            marker="o",
            label=weapon.name,
            linestyle=next(line_styles),
            alpha=0.75,
        )

    plt.title(
        "BF6 Weapons ({weapon_class}) - {description}".format(
            weapon_class=preset.weapon_class, description=preset.description()
        )
    )
    plt.xlabel("Distance")
    # RANGES.insert(0, "")
    plt.xticks(
        range(len(RANGES)) if evenly_spaces_ranges else list(RANGES.values()),
        list(RANGES.keys()),
        rotation=45,
    )
    plt.ylabel("TTK (ms)")
    if fixed_ticks:
        plt.yticks(fixed_ticks)
    plt.legend(fontsize=8, bbox_to_anchor=(1.02, 1), loc="upper left")
    # plt.grid(True, which="major", linestyle="--", linewidth=0.50, alpha=0.85)
    plt.tight_layout()
    if show:
        plt.show()


def main():
    argparser = argparse.ArgumentParser()
    argparser.add_argument(
        "-a", "--all", dest="generate_all", action="store_true", default=False
    )
    argparser.add_argument("-w", "--weapons", dest="weapons", nargs="+", default=None)
    argparser.add_argument(
        "-c", "--class", dest="weapon_class", default=WeaponClass.All
    )
    argparser.add_argument(
        "--health-profile", dest="health_profile", default=HealthProfileType.Multiplayer
    )
    argparser.add_argument(
        "--damage-profile", dest="damage_profile", default=DamageProfileType.Body
    )
    argparser.add_argument("--plot-type", dest="plot_type", default=PlotType.TTK)

    # Health Profile overrides.
    argparser.add_argument("--health", dest="health", default=None)
    argparser.add_argument("--plates", dest="plates", default=None)
    argparser.add_argument("--plate_health", dest="plate_health", default=None)
    argparser.add_argument("--platedr", dest="plate_damage_reduction", default=None)

    # Damage Profile overrides.
    argparser.add_argument("--headshots", dest="headshots", default=None)
    argparser.add_argument("--hsmult", dest="headshot_multiplier", default=None)
    argparser.add_argument("--misses", dest="misses", default=None)

    argparser.add_argument("--ymin", dest="y_tick_min", default=None)
    argparser.add_argument("--ymax", dest="y_tick_max", default=600)
    argparser.add_argument("--ystep", dest="y_tick_step", default=50)
    argparser.add_argument(
        "--evenly-spaces-ranges",
        dest="evenly_spaces_ranges",
        action="store_true",
        default=False,
    )

    args = argparser.parse_args()

    all_weapons = read_weapon_stats()
    y_ticks = None
    if args.y_tick_min:
        y_ticks = range(
            int(args.y_tick_min),
            args.y_tick_max and int(args.y_tick_max) or 600,
            args.y_tick_step and int(args.y_tick_step) or 50,
        )

    if args.generate_all:
        for weapon_class in WeaponClass:
            weapons_to_plot: list[Weapon] = []
            if weapon_class == WeaponClass.All:
                weapons_to_plot = all_weapons
            else:
                for weapon in all_weapons:
                    if weapon.weapon_class == weapon_class:
                        weapons_to_plot.append(weapon)

            for health_profile in HEALTH_PROFILES.values():
                for damage_profile in DAMAGE_PROFILES.values():
                    preset = Preset("", health_profile, damage_profile, weapon_class)

                    file_name = "Plots\\BF6-{health_profile}-{damage_profile}-{weapon_class}.png".format(
                        health_profile=health_profile.name,
                        damage_profile=damage_profile.name.replace(" ", "").replace(
                            "+", "And"
                        ),
                        weapon_class=weapon_class,
                    )
                    print("Generating:", file_name)

                    plot(
                        weapons_to_plot,
                        preset,
                        plot_type=args.plot_type,
                        fixed_ticks=y_ticks,
                        evenly_spaces_ranges=args.evenly_spaces_ranges,
                        show=False,
                    )
                    plt.savefig(file_name)
                    plt.close()

    else:
        weapon_class = WeaponClass.Specific if args.weapons else args.weapon_class
        health_profile_type = args.health_profile or HealthProfileType.Multiplayer
        damage_profile_type = args.damage_profile or DamageProfileType.Body

        health_profile = HEALTH_PROFILES[health_profile_type]
        health_profile.health = (
            args.health and int(args.health) or health_profile.health
        )
        health_profile.plates = (
            args.plates and int(args.plates) or health_profile.plates
        )
        health_profile.plate_health = (
            args.plate_health and int(args.plate_health) or health_profile.plate_health
        )
        if args.plate_damage_reduction is not None:
            health_profile.plate_damage_reduction = float(args.plate_damage_reduction)

        damage_profile = DAMAGE_PROFILES[damage_profile_type]
        damage_profile.headshots = (
            args.headshots and int(args.headshots) or damage_profile.headshots
        )
        damage_profile.headshot_multiplier_override = (
            args.headshot_multiplier
            and float(args.headshot_multiplier)
            or damage_profile.headshot_multiplier_override
        )
        damage_profile.misses = (
            args.misses and int(args.misses) or damage_profile.misses
        )

        preset = Preset("", health_profile, damage_profile, weapon_class)

        weapons_to_plot = []
        match weapon_class:
            case WeaponClass.All:
                weapons_to_plot = all_weapons
            case WeaponClass.Specific:
                for weapon in all_weapons:
                    if weapon.name in args.weapons:
                        weapons_to_plot.append(weapon)
            case _:
                for weapon in all_weapons:
                    if weapon.weapon_class == weapon_class:
                        weapons_to_plot.append(weapon)

        plot(
            weapons_to_plot,
            preset,
            plot_type=args.plot_type,
            fixed_ticks=y_ticks,
            evenly_spaces_ranges=args.evenly_spaces_ranges,
        )


if __name__ == "__main__":
    main()
