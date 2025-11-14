import argparse
import math
import csv
import matplotlib.pyplot as plt
from enum import StrEnum
from itertools import cycle

STATS_FILE = "Stats.csv"
DISTANCES = [
    "0 m",
    "10 m",
    # "15 m",  # Same as previous.
    "20 m",
    # "25 m",  # Same as previous.
    # "35 m",  # Same as previous.
    "40 m",
    # "50 m",  # Same as previous.
    # "55 m",  # Same as previous.
    # "70 m",  # Same as previous.
    "70+ m",
]


class WeaponClass(StrEnum):
    All = "All"
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
    def __init__(self, name, health, plates, plate_health, plate_damage_reduction):
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


class Weapon:
    def __init__(self, row):
        self.name = row["Weapon"]
        self.weapon_class = row["Class"]
        self.headshot_multiplier = float(row["HS Mult"])
        self.rpm = int(row["RPM"])
        self.shot_intverval = 60_000 / self.rpm

        self.damage_falloffs = []
        for distance in DISTANCES:
            self.damage_falloffs.append(float(row[distance]))


class DamageProfile:
    def __init__(self, name, headshots, headshot_multiplier_override=None, misses=0):
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


class Preset:
    def __init__(
        self,
        name,
        health_profile,
        damage_profile,
        weapon_class=WeaponClass.All,
    ):
        self.name = name
        self.health_profile = health_profile
        self.damage_profile = damage_profile
        self.weapon_class = weapon_class

    def calc_ttk(self, weapon):
        headshot_multiplier = (
            self.damage_profile.headshot_multiplier_override
            or weapon.headshot_multiplier
        )

        ttks = []
        for damage in weapon.damage_falloffs:
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
            ttk = (total_shots - 1) * weapon.shot_intverval
            ttks.append(ttk)
        return ttks

    def description(self):
        description = "{health_profile} ({health} HP, {plates} Plate(s), {plate_damage_reduction}% Plate DR), {damage_profile}".format(
            health_profile=self.health_profile.name,
            health=self.health_profile.health,
            plates=self.health_profile.plates,
            plate_damage_reduction=self.health_profile.plate_damage_reduction * 100,
            damage_profile=self.damage_profile.name,
        )

        return description


def read_weapon_stats():
    weapons = []
    with open(STATS_FILE) as csvfile:
        weapon_stats_reader = csv.DictReader(csvfile)
        for row in weapon_stats_reader:
            # print(row)
            weapon = Weapon(row)
            weapons.append(weapon)
    return weapons


def plot(weapons, preset, fixed_ticks=None, show=True):
    plt.figure(figsize=(10, 6))
    line_styles = cycle([":", "-."])
    for weapon in weapons:
        y = preset.calc_ttk(weapon)
        # y.insert(0, y[0])
        y.append(y[-1])
        x = list(range(len(y)))

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
    # DISTANCES.insert(0, "")
    plt.xticks(range(len(DISTANCES)), DISTANCES, rotation=45)
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
    argparser.add_argument("-a", "--all", dest="generate_all", action="store_true")
    argparser.add_argument(
        "-c", "--class", dest="weapon_class", default=WeaponClass.All
    )
    argparser.add_argument(
        "--healthprofile", dest="health_profile", default=HealthProfileType.Multiplayer
    )
    argparser.add_argument(
        "--damageprofile", dest="damage_profile", default=DamageProfileType.Body
    )

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
            weapons_to_plot = []
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
                        show=False,
                        fixed_ticks=y_ticks,
                    )
                    plt.savefig(file_name)
                    plt.close()

    else:
        weapon_class = args.weapon_class
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
        if weapon_class == WeaponClass.All:
            weapons_to_plot = all_weapons
        else:
            for weapon in all_weapons:
                if weapon.weapon_class == weapon_class:
                    weapons_to_plot.append(weapon)

        plot(
            weapons_to_plot,
            preset,
            fixed_ticks=y_ticks,
        )


if __name__ == "__main__":
    main()
