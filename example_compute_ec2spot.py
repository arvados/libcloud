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
NODE_NAME = 'test-spot-node'
TAGS = {'Name': NODE_NAME}
TERMINATED_TAGS = {'Name': 'terminated_{0}'.format(NODE_NAME)}


def create_spot_request(accessid, secretkey):
    cls = get_driver(Provider.EC2)
    driver = cls(accessid, secretkey, region=REGION)

    sizes = driver.list_sizes()
    size = [s for s in sizes if s.id == SIZE_ID][0]
    image = NodeImage(id=AMI_ID, name=None, driver=driver)

    # create the spot instance
    req = driver.request_spot_instances(
        image=image,
        size=size,
        spot_price=(size.price * PRICE_FACTOR),
        keyname=KEYPAIR_NAME,
        security_groups=SECURITY_GROUP_NAMES)

    # wait for the spot request to be fullfilled
    while req.state == EC2SpotRequestState.OPEN:
        print(req.message)
        time.sleep(5)
        req = driver.ex_list_spot_requests(spot_request_ids=[req.id])[0]

    # clean up after ourselves if the request was fullfilled
    if req.state == EC2SpotRequestState.ACTIVE:
        print(req.message)
        print(req.instance_id)

        # tag the node
        node = driver.list_nodes(ex_node_ids=[req.instance_id])[0]
        print(driver.ex_create_tags(node, TAGS))

        # cancel the spot request
        print(driver.ex_cancel_spot_instance_request(req))

        # destroy the node and update the tags
        print(driver.destroy_node(node))
        print(driver.ex_create_tags(node, TERMINATED_TAGS))

        # check the spot request is cancelled
        req = driver.ex_list_spot_requests(spot_request_ids=[req.id])[0]
        assert req.state == EC2SpotRequestState.CANCELLED


def main():
    accessid = os.getenv('ACCESSID')
    secretkey = os.getenv('SECRETKEY')

    if accessid and secretkey:
        create_spot_request(accessid, secretkey)
    else:
        print('ACCESSID and SECRETKEY are sourced from the environment')

if __name__ == "__main__":
    main()
