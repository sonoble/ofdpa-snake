#! /usr/bin/env python
############################################################
# <bsn.cl fy=2015 v=onl>
#
#           Copyright 2016 Big Switch Networks, Inc.
#
# Licensed under the Eclipse Public License, Version 1.0 (the
# "License"); you may not use this file except in compliance
# with the License. You may obtain a copy of the License at
#
#        http://www.eclipse.org/legal/epl-v10.html
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
# either express or implied. See the License for the specific
# language governing permissions and limitations under the
# License.
#
# </bsn.cl>
############################################################
""" 
Set up OF-DPA groups and flows configuring a virtual patch panel between two
ports or optionally all of the ports (for a snake test).

This script invokes OF-DPA API services via RPC. The RPC calls are served by the ofdpa
process running on the switch.

"""
from OFDPA_python import *

def main(start_port=1, end_port=48, vlan_id=10):
    # first initialize OF-DPA
    rc = ofdpaClientInitialize("OFDPA_patch")
    if rc != OFDPA_E_NONE:
        raise Exception("Problem initializing OFDPA - " + str(rc))

    if end_port <= start_port:
        raise Exception("The start_port=" + str(start_port) + " must be less than the end_port=" + str(end_port))
    if ((end_port - start_port) % 2) == 0:
        raise Exception("Must have an even number of ports. start_port=" + str(start_port) + ", end_port=" + str(end_port) + " has count of " + str(end_port - start_port + 1) + " ports")
    if vlan_id < 0 or vlan_id > 4095:
        raise Exception("Must specify a valid VLAN. Got vlan_id=" + str(vlan_id) + ". (Use VLAN 0 to specify untagged.)")

    # create snake assuming start_port is input and end_port is output
    skip = 0 # first two ports are connected, then next two, etc.
    for in_port in range(start_port, end_port):
        if skip == 0:
            skip = 1
        else:
            skip = 0
            continue
        set_vlan(in_port, vlan_id)
        set_vlan(in_port + 1, vlan_id)
        set_acl(in_port, in_port + 1, vlan_id)
        set_acl(in_port + 1, in_port, vlan_id)

def set_vlan(in_port, vlan_id):
    # tagged VLAN flow (must have this for untagged to work)
    vlanFlowEntry = ofdpaFlowEntry_t()
    ofdpaFlowEntryInit(OFDPA_FLOW_TABLE_ID_VLAN, vlanFlowEntry)
    vlanFlowEntry.flowData.vlanFlowEntry.gotoTableId = OFDPA_FLOW_TABLE_ID_TERMINATION_MAC
    vlanFlowEntry.flowData.vlanFlowEntry.match_criteria.inPort = in_port
    vlanFlowEntry.flowData.vlanFlowEntry.match_criteria.vlanId = (OFDPA_VID_PRESENT | (1 if vlan_id == 0 else vlan_id))
    vlanFlowEntry.flowData.vlanFlowEntry.match_criteria.vlanIdMask = (OFDPA_VID_PRESENT | OFDPA_VID_EXACT_MASK)
    vlanFlowEntry.flowData.vlanFlowEntry.setVlanIdAction = 1
    vlanFlowEntry.flowData.vlanFlowEntry.newVlanId = (1 if vlan_id == 0 else vlan_id) # use VLAN 1 internally for untagged

    ofdpaFlowAdd(vlanFlowEntry)

    # untagged VLAN flow
    if vlan_id == 0:
        vlanFlowEntry = ofdpaFlowEntry_t()
        ofdpaFlowEntryInit(OFDPA_FLOW_TABLE_ID_VLAN, vlanFlowEntry)
        vlanFlowEntry.flowData.vlanFlowEntry.gotoTableId = OFDPA_FLOW_TABLE_ID_TERMINATION_MAC
        vlanFlowEntry.flowData.vlanFlowEntry.match_criteria.inPort = in_port
        vlanFlowEntry.flowData.vlanFlowEntry.match_criteria.vlanId = OFDPA_VID_NONE
        vlanFlowEntry.flowData.vlanFlowEntry.match_criteria.vlanIdMask = 0x1fff # TODO is this really correct? Should be 0x0fff w/o present bit
        vlanFlowEntry.flowData.vlanFlowEntry.setVlanIdAction = 1
        vlanFlowEntry.flowData.vlanFlowEntry.newVlanId = (1 if vlan_id == 0 else vlan_id) # use VLAN 1 internally for untagged

        ofdpaFlowAdd(vlanFlowEntry)

def set_acl(in_port, out_port, vlan_id):
    # L2 interface group and bucket
    groupId_p = new_uint32_tp()
    l2IfaceGroupEntry = ofdpaGroupEntry_t()
    l2IfaceGroupBucket = ofdpaGroupBucketEntry_t()

    ofdpaGroupTypeSet(groupId_p, OFDPA_GROUP_ENTRY_TYPE_L2_INTERFACE)
    ofdpaGroupVlanSet(groupId_p, (1 if vlan_id == 0 else vlan_id)) # use VLAN 1 internally for untagged
    ofdpaGroupPortIdSet(groupId_p, out_port)

    l2IfaceGroupEntry.groupId = uint32_tp_value(groupId_p)
    l2IfaceGroupBucket.groupId = l2IfaceGroupEntry.groupId
    l2IfaceGroupBucket.bucketIndex = 0
    l2IfaceGroupBucket.bucketData.l2Interface.outputPort = out_port
    l2IfaceGroupBucket.bucketData.l2Interface.popVlanTag = (1 if vlan_id == 0 else 0) # pop for untagged only

    # must add bucket before group
    ofdpaGroupAdd(l2IfaceGroupEntry)
    ofdpaGroupBucketEntryAdd(l2IfaceGroupBucket)

    # ACL flow
    aclForwardFlowEntry = ofdpaFlowEntry_t()
    ofdpaFlowEntryInit(OFDPA_FLOW_TABLE_ID_ACL_POLICY, aclForwardFlowEntry)
    aclForwardFlowEntry.flowData.policyAclFlowEntry.match_criteria.inPort = in_port
    aclForwardFlowEntry.flowData.policyAclFlowEntry.match_criteria.inPortMask = OFDPA_INPORT_EXACT_MASK
    aclForwardFlowEntry.flowData.policyAclFlowEntry.groupID = l2IfaceGroupEntry.groupId

    ofdpaFlowAdd(aclForwardFlowEntry)

if __name__ == '__main__': main()
