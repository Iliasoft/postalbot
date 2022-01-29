from suds.client import Client
from suds import *
from suds.transport import TransportError


class RussianPostAPI:
    def __init__(self):
        pass

    @staticmethod
    def get_shipment_data(barcode, login, password):

        url = 'https://tracking.russianpost.ru/rtm34?wsdl'
        client = Client(url, retxml=True, headers={'Content-Type': 'application/soap+xml;'}, location='https://tracking.russianpost.ru/rtm34/Service.svc')

        message = \
        """<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope" xmlns:oper="http://russianpost.org/operationhistory" xmlns:data="http://russianpost.org/operationhistory/data" xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/">
           <soap:Header/>
           <soap:Body>
              <oper:getOperationHistory>
                 <data:OperationHistoryRequest>
                    <data:Barcode>""" + str(barcode) + """</data:Barcode>
                    <data:MessageType>0</data:MessageType>
                    <data:Language>RUS</data:Language>
                 </data:OperationHistoryRequest>
                 <data:AuthorizationHeader soapenv:mustUnderstand="1">
                    <data:login>""" + login + """</data:login>
                    <data:password>""" + password + """</data:password>
                 </data:AuthorizationHeader>
              </oper:getOperationHistory>
           </soap:Body>
        </soap:Envelope>"""
        try:
            result = client.service.getOperationHistory(__inject={'msg':byte_str(message)})
            #sFile = open("otv1.xml", 'w')
            #sFile.write(str(result))
            #sFile.close()
            return result

        except:
            return None
