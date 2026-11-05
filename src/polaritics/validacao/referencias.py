"""Valores publicados por terceiros usados só para comparação (nunca como insumo do cálculo)."""

# Radar do Congresso (Congresso em Foco): deputados votaram com o governo Lula em 72% das
# votações em plenário em 2023 e 2024.
RADAR_GOVERNISMO_2023_2024 = 0.72
RADAR_FONTE = "https://www.congressoemfoco.com.br/tema/radar-do-congresso"

# GPS Partidário 2026 (Folha de S.Paulo/DeltaFolha), famílias da régua combinada publicadas no
# README do repositório. Os cortes entre famílias ficam em 4,5 e 7,0 na escala dos especialistas.
GPS_FONTE = "https://github.com/deltafolha/gps-partidario-2026"
GPS_CORTES = (4.5, 7.0)
GPS_FAMILIAS = {
    **dict.fromkeys(
        ["PSTU", "UP", "PCB", "PSOL", "PT", "PCdoB", "REDE", "PV", "PSB", "PDT"], "esquerda"
    ),
    **dict.fromkeys(["MDB", "PSD", "AVANTE", "SOLIDARIEDADE", "AGIR", "MOBILIZA"], "centro"),
    **dict.fromkeys(
        [
            "PP",
            "CIDADANIA",
            "PRD",
            "REPUBLICANOS",
            "PODE",
            "UNIÃO",
            "PSDB",
            "PMB",
            "DC",
            "MISSÃO",
            "PRTB",
            "PL",
            "NOVO",
        ],
        "direita",
    ),
}
