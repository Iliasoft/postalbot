This Telegram Pochtabot is Ilias Eldarov's MIPT Software Development course project.

Capabilities:
- notifies user each time a tracked shipment changes location in process of delivery (bot is requesting status from postal API every 30 mins)
- list all user' shipments that are ready for collection i.e. have arrived to post office but not delivered
- tells user current status of shipment
- distinguishes users amonth each other along with their shipments (based on chat.id)

The bot is based on Russian Post' API available via Web-Service, see https://tracking.pochta.ru/specification/single
