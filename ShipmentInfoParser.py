import xml.etree.ElementTree as ET
import time
from time import gmtime, strftime, sleep

class ShipmentInfo:

    def __init__(self):

        self.departure_index = ''
        self.destination_index = ''
        self.sender = ''
        self.receiver = ''
        self.type = ''
        self.weight = 0
        self.events = []

    def __str__(self):
        return f"{self.type} ({self.weight} g.) \n" + \
               strftime("%a, %d %b %H:%M", self.events[-1][3]) + " : " \
               f"{self.events[-1][2]}, {self.events[-1][5]}" + \
               "\nDeparted: " + strftime("%a, %d %b %H:%M", self.events[0][3]) + \
               f" from {self.departure_index}, {self.sender}" + \
               f"\nTo: {self.destination_index}, {self.receiver}"


class ShipmentInfoParser:

    @staticmethod
    def parse_xml(xml):
        # if we have empty XML than lets return Nothing
        if not xml:
            return None

        shipment = ShipmentInfo()

        # envelope = ET.parse('otv.xml').getroot()
        envelope = ET.fromstring(xml)
        body = envelope[0]
        getOperationHistoryResponse = body[0]
        operationHistoryData = getOperationHistoryResponse[0]

        first_event = True
        for historyRecord in operationHistoryData:

            date_time = ShipmentInfoParser.get_att(historyRecord, ["OperationParameters", "OperDate"])
            # 2021-12-14T08:48:36.000+03:00
            if date_time:
                try:
                    date_time = time.strptime(date_time[:19], "%Y-%m-%dT%H:%M:%S")
                except ValueError:
                    date_time = None

            shipment.events.append((
                int(ShipmentInfoParser.get_att(historyRecord, ["OperationParameters", "OperType", "Id"])),
                ShipmentInfoParser.get_att(historyRecord, ["OperationParameters", "OperType", "Name"]),
                ShipmentInfoParser.get_att(historyRecord, ["AddressParameters", "OperationAddress", "Description"]),
                date_time,
                int(ShipmentInfoParser.get_att(historyRecord, ["OperationParameters", "OperAttr", "Id"])),
                ShipmentInfoParser.get_att(historyRecord, ["OperationParameters", "OperAttr", "Name"]),
            )
            )
            if not first_event:
                continue

            shipment.departure_index = shipment.events[0][2]
            shipment.destination_index = ShipmentInfoParser.get_att(historyRecord,
                                                          ["AddressParameters", "DestinationAddress", "Description"])
            shipment.sender = ShipmentInfoParser.get_att(historyRecord, ["UserParameters", "Sndr"])
            shipment.receiver = ShipmentInfoParser.get_att(historyRecord, ["UserParameters", "Rcpn"])
            shipment.type = ShipmentInfoParser.get_att(historyRecord, ["ItemParameters", "ComplexItemName"])
            shipment.weight = ShipmentInfoParser.get_att(historyRecord, ["ItemParameters", "Mass"])

            first_event = False

        return shipment

    @staticmethod
    def get_att(node, path):
        if len(path) == 2:
            return ShipmentInfoParser.get_att2(node, path)
        elif len(path) == 3:
            return ShipmentInfoParser.get_att3(node, path)
        else:
            raise NotImplemented #

    @staticmethod
    def get_att2(node, path):
        for child0 in node:
            if path[0] in child0.tag:
                for child1 in child0:
                    if path[1] in child1.tag:
                        return child1.text
        return None

    @staticmethod
    def get_att3(node, path):
        for child0 in node:
            if path[0] in child0.tag:
                for child1 in child0:
                    if path[1] in child1.tag:
                        for child2 in child1:
                            if path[2] in child2.tag:
                                return child2.text
        return None

'''
AddressParameters->DestinationAddress->Index 'Kuda'
AddressParameters->OperationAddress->Index 'otkuda'
ItemParameters->ComplexItemName  'pismo'
ItemParameters->MailCtg->Mass
UserParameters->Sndr #'oppravitel
UserParameters->Rcpn # poluchatel

OperationParameters->OperType->Name  'acceptance'
OperationParameters->OperAttr->OperDate "date"
'''