"""Every outside source the site cites, and src() to link one next to a claim."""

# Every outside source the project relies on, defined once: key -> (group, short label, title, url, what it backs up).
# The References tab lists them all; src() puts a short link next to a claim anywhere else on the site.
SOURCES = {
    "gen_report": ("Data", "IESO", "IESO: Generator Output and Capability report",
                   "https://reports-public.ieso.ca/public/GenOutputCapabilityMonth/",
                   "Hourly output and capability of every generator of 20 MW or more, May 2019 to Sep 2026. "
                   "Almost every number on the dashboard comes from it."),
    "intertie_report": ("Data", "IESO", "IESO: Intertie Schedule and Flow report",
                        "https://reports-public.ieso.ca/public/IntertieScheduleFlowYear/",
                        "Hourly imports and exports with Ontario's neighbours."),
    "hoep_report": ("Data", "IESO", "IESO: Hourly Ontario Energy Price (HOEP) report",
                    "https://reports-public.ieso.ca/public/PriceHOEPPredispOR/",
                    "Hourly wholesale price in the old market, until April 2025."),
    "ozp_report": ("Data", "IESO", "IESO: Day-ahead Ontario zonal price report",
                   "https://reports-public.ieso.ca/public/DAHourlyOntarioZonalPrice/",
                   "Hourly wholesale price in the new market, from 31 July 2026 (IESO keeps about 90 days online)."),
    "ieso_markets": ("How the market works", "IESO", "IESO: Introduction to Ontario's Physical Markets (training guide, 2005)",
                     "https://www.oeb.ca/documents/msp/consultation_introontariophysicalmkts.pdf",
                     "How the price is set: offers are stacked from cheapest to most expensive, the last one needed sets "
                     "the price, and every generator is paid that same price. Offers are based on the cost of making one "
                     "more MWh, which is mostly fuel. Also: electricity can't be stored in bulk, so supply must match use "
                     "at every moment."),
    "ieso_ontario_price": ("How the market works", "IESO", "IESO: Understanding the Ontario Price",
                           "https://ieso.ca/-/media/Files/IESO/Document-Library/learn/understanding-the-ontario-price.pdf",
                           "The new market price replaced the HOEP. The hourly market price covers only part of the cost of "
                           "electricity; the Global Adjustment covers the rest, including building and maintaining power plants."),
    "ieso_ga": ("How the market works", "IESO", "IESO: Global Adjustment",
                "https://ieso.ca/Power-Data/Price-Overview/Global-Adjustment",
                "What the Global Adjustment pays for, and why it goes up when the market price goes down."),
    "ieso_mrp": ("How the market works", "IESO", "IESO: Market Renewal Program",
                 "https://www.ieso.ca/Sector-Participants/Market-Operations/Marketplace-Training/MRP-Training-Materials",
                 "Ontario's new market went live on 1 May 2025."),
    "cns_basics": ("Reactors", "CNS", "Canadian Nuclear Society: Basics of nuclear",
                   "https://cns-snc.ca/learn-nuclear/basics-of-nuclear/",
                   "How a reactor makes electricity: splitting atoms releases heat, the heat makes steam, the steam spins "
                   "a turbine, and the turbine drives a generator."),
    "wna_economics": ("Reactors", "WNA", "World Nuclear Association: Economics of nuclear power",
                      "https://world-nuclear.org/information-library/economic-aspects/economics-of-nuclear-power",
                      "Nuclear plants are expensive to build but cheap to run: fuel is a small share of their cost."),
    "wnn_darlington": ("Reactors", "WNN", "World Nuclear News: OPG gets go-ahead for Darlington refurbishment (2016)",
                       "https://world-nuclear-news.org/articles/opg-gets-go-ahead-for-darlington-refurbishment",
                       "A refurbishment lets a reactor run for about another 30 years."),
    "ieso_2018": ("Reactors", "IESO", "IESO: 2018 year-end data",
                  "https://ieso.ca/Corporate-IESO/Media/Year-End-Data/2018",
                  "Bruce Power can cut each reactor's output by about 300 MW when Ontario has more power than it needs."),
    "opg_esg": ("Emissions", "OPG", "Ontario Power Generation: 2021 ESG report",
                "https://www.opg.com/wp-content/uploads/2022/08/OPG_ESG_Report_2021_FINAL-ua.pdf",
                "The emissions factor used for gas plants: 450 g of CO2 per kWh, which is 0.45 t per MWh."),
    "unece": ("Emissions", "UNECE", "UNECE: Life Cycle Assessment of Electricity Generation Options (2021)",
              "https://unece.org/sites/default/files/2021-11/LCA_final.pdf",
              "Gas combined-cycle plants release about 0.40 to 0.51 t of CO2 per MWh over their life, and nuclear about "
              "0.005 t. The top of the range used here (0.55) is an allowance for older, less efficient gas plants."),
    "oeb_home": ("Everyday comparisons", "OEB", "Ontario Energy Board: electricity prices news release (2019)",
                 "https://www.oeb.ca/node/2419",
                 "A typical Ontario household uses 700 kWh a month: about 1 kW on average, so 1 MW is roughly 1,000 homes."),
    "epa_car": ("Everyday comparisons", "EPA", "US EPA: Greenhouse gas emissions from a typical passenger vehicle",
                "https://www.epa.gov/greenvehicles/greenhouse-gas-emissions-typical-passenger-vehicle",
                "A typical car releases about 4.6 t of CO2 a year."),
    "bruce_vbo": ("Outage records", "Bruce Power", "Bruce Power: Bruce B planned Vacuum Building Outage begins (2024)",
                  "https://www.brucepower.com/?p=24915",
                  "The April 2024 shutdown of all Bruce B reactors was a planned vacuum building outage: the "
                  "reactors share one safety building, and inspecting it needs every connected reactor shut down."),
    "cnsc_status": ("Outage records", "CNSC", "Canadian Nuclear Safety Commission: Status Reports on Power Reactors",
                    "https://www.cnsc-ccsn.gc.ca/eng/the-commission/meetings/",
                    "Presented at each Commission meeting; they say which reactors are shut down and whether the "
                    "outage is planned or forced. Used for the small answer key of planned and forced outages."),
}


def src(key):
    _, label, _, url, _ = SOURCES[key]
    return f"([{label}]({url}))"
