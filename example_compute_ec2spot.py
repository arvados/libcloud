import time
import os
from libcloud.compute.types import Provider
from libcloud.compute.providers import get_driver
from libcloud.compute.base import NodeImage
from libcloud.compute.drivers.ec2 import EC2SpotRequestState

SIZE_ID = 't2.micro'
AMI_ID = 'ami-4e79ed36'
REGION = 'us-west-2'
KEYPAIR_NAME = 'mykey'
SECURITY_GROUP_NAMES = ['default', 'ssh']
PRICE_FACTOR = 0.5

def create_spot_request(accessid, secretkey):
    cls = get_driver(Provider.EC2)
    driver = cls(accessid, secretkey, region=REGION)

    sizes = driver.list_sizes()
    size = [s for s in sizes if s.id == SIZE_ID][0]
    image = NodeImage(id=AMI_ID, name=None, driver=driver)

    # create the spot instance
    node = driver.create_node(
        image=image,
        size=size,
        ex_spot_price=(size.price * PRICE_FACTOR),
        ex_keyname=KEYPAIR_NAME,
        ex_security_groups=SECURITY_GROUP_NAMES)

    tries = 3
    while node.id is None and tries > 0:
        print("Spot instance not started yet - Request '%s'" % (node.spot_request_id))
        tries -= 1
        time.sleep(10)

    if node.id is None:
        print("Spot instance not created. Cancelling request '%s'" % \
            (node.spot_request_id))
    else:
        print("Spot instance created: '%s' - State: '%s'. Destroying node" % \
            (node.id, node.state))

    driver.destroy_node(node)

    while node.spot_request.state == EC2SpotRequestState.ACTIVE:
        print("Waiting for the Spot Request to be cancelled (State: %s)" % \
            (node.spot_request.state))
        time.sleep(10)

    print("Done")

def main():
    accessid = os.getenv('ACCESSID')
    secretkey = os.getenv('SECRETKEY')

    if accessid and secretkey:
        create_spot_request(accessid, secretkey)
    else:
        print('ACCESSID and SECRETKEY are sourced from the environment')

if __name__ == "__main__":
    main()
