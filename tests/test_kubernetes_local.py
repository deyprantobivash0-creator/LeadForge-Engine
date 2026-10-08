"""Local deployment safety gates must fail before any Kubernetes mutation."""
import json
from types import SimpleNamespace
import pytest
from scripts import kubernetes_local as local


def replies(monkeypatch, context='docker-desktop', endpoint='https://127.0.0.1:49175', ready='True'):
    calls=[]
    nodes={'items':[{'metadata':{'name':'desktop-control-plane'},'status':{'conditions':[{'type':'Ready','status':ready}]}}]}
    output=[context, 'Kubernetes control plane is running at '+endpoint, json.dumps(nodes)]
    def run(args, **kwargs):
        calls.append(args)
        return SimpleNamespace(stdout=output[len(calls)-1],returncode=0)
    monkeypatch.setattr(local,'run',run)
    monkeypatch.setattr(local,'executable',lambda name:name)
    return calls


@pytest.mark.parametrize('context,endpoint,ready,reads',[
    ('cloud-cluster','https://127.0.0.1:49175','True',1),
    ('docker-desktop','https://cloud.invalid:6443','True',2),
    ('docker-desktop','https://127.0.0.1:49175','False',3),
],ids=['wrong-context','remote-endpoint','node-not-ready'])
def test_deploy_refuses_before_mutation(monkeypatch,context,endpoint,ready,reads):
    calls=replies(monkeypatch,context,endpoint,ready)
    with pytest.raises(RuntimeError,match='STOP'):
        local.deploy()
    assert len(calls)==reads
    assert all('apply' not in call and 'create' not in call for call in calls)


def test_context_and_node_names_can_differ(monkeypatch):
    calls=replies(monkeypatch)
    local.safety()
    assert len(calls)==3


def test_existing_secret_mismatch_refuses_rotation(monkeypatch):
    calls=[]
    def kubectl(*args,**kwargs):
        calls.append(args)
        return SimpleNamespace(returncode=0,stdout=json.dumps({'data':{'app_password':'existing-synthetic-placeholder'}}))
    monkeypatch.setattr(local,'kubectl',kubectl)
    with pytest.raises(RuntimeError,match='coordinate rotation'):
        local.ensure_secret({'metadata':{'name':'leadforge-credentials'},'data':{'app_password':'different-synthetic-placeholder'}})
    assert len(calls)==1 and calls[0][0]=='get'
