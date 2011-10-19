# coding: utf-8

import os, re, datetime
from tests.shared import assertException, getEmptyDeck, testDir, \
    getUpgradeDeckPath
from anki.stdmodels import addBasicModel
from anki.consts import *

from anki import Deck

newPath = None
newMod = None

def test_create():
    global newPath, newMod
    path = "/tmp/test_attachNew.anki2"
    try:
        os.unlink(path)
    except OSError:
        pass
    deck = Deck(path)
    # for open()
    newPath = deck.path
    deck.close()
    newMod = deck.mod
    del deck

def test_open():
    deck = Deck(newPath)
    assert deck.mod == newMod
    deck.close()

def test_openReadOnly():
    # non-writeable dir
    assertException(Exception,
                    lambda: Deck("/attachroot.anki2"))
    # reuse tmp file from before, test non-writeable file
    os.chmod(newPath, 0)
    assertException(Exception,
                    lambda: Deck(newPath))
    os.chmod(newPath, 0666)
    os.unlink(newPath)

def test_factAddDelete():
    deck = getEmptyDeck()
    # add a fact
    f = deck.newFact()
    f['Front'] = u"one"; f['Back'] = u"two"
    n = deck.addFact(f)
    assert n == 1
    deck.rollback()
    assert deck.cardCount() == 0
    # try with two cards
    f = deck.newFact()
    f['Front'] = u"one"; f['Back'] = u"two"
    m = f.model()
    m['tmpls'][1]['actv'] = True
    deck.models.save(m)
    n = deck.addFact(f)
    assert n == 2
    # check q/a generation
    c0 = f.cards()[0]
    assert re.sub("</?.+?>", "", c0.q()) == u"one"
    # it should not be a duplicate
    for p in f.problems():
        assert not p
    # now let's make a duplicate and test uniqueness
    f2 = deck.newFact()
    f2.model()['flds'][1]['req'] = True
    f2['Front'] = u"one"; f2['Back'] = u""
    p = f2.problems()
    assert p[0] == "unique"
    assert p[1] == "required"
    # try delete the first card
    cards = f.cards()
    id1 = cards[0].id; id2 = cards[1].id
    assert deck.cardCount() == 2
    assert deck.factCount() == 1
    deck.remCards([id1])
    assert deck.cardCount() == 1
    assert deck.factCount() == 1
    # and the second should clear the fact
    deck.remCards([id2])
    assert deck.cardCount() == 0
    assert deck.factCount() == 0

def test_fieldChecksum():
    deck = getEmptyDeck()
    f = deck.newFact()
    f['Front'] = u"new"; f['Back'] = u"new2"
    deck.addFact(f)
    assert deck.db.scalar(
        "select csum from fsums") == int("c2a6b03f", 16)
    # empty field should have no checksum
    f['Front'] = u""
    f.flush()
    assert deck.db.scalar(
        "select count() from fsums") == 0
    # changing the val should change the checksum
    f['Front'] = u"newx"
    f.flush()
    assert deck.db.scalar(
        "select csum from fsums") == int("302811ae", 16)
    # turning off unique and modifying the fact should delete the sum
    m = f.model()
    m['flds'][0]['uniq'] = False
    deck.models.save(m)
    f.flush()
    assert deck.db.scalar(
        "select count() from fsums") == 0
    # and turning on both should ensure two checksums generated
    m['flds'][0]['uniq'] = True
    m['flds'][1]['uniq'] = True
    deck.models.save(m)
    f.flush()
    assert deck.db.scalar(
        "select count() from fsums") == 2

def test_upgrade():
    dst = getUpgradeDeckPath()
    print "upgrade to", dst
    deck = Deck(dst)
    # creation time should have been adjusted
    d = datetime.datetime.fromtimestamp(deck.crt)
    assert d.hour == 4 and d.minute == 0
    # 3 new, 2 failed, 1 due
    deck.conf['counts'] = COUNT_REMAINING
    assert deck.sched.cardCounts() == (3,2,1)
    # now's a good time to test the integrity check too
    deck.fixIntegrity()

def test_selective():
    deck = getEmptyDeck()
    f = deck.newFact()
    f['Front'] = u"1"; f.tags = ["one", "three"]
    deck.addFact(f)
    f = deck.newFact()
    f['Front'] = u"2"; f.tags = ["two", "three", "four"]
    deck.addFact(f)
    f = deck.newFact()
    f['Front'] = u"3"; f.tags = ["one", "two", "three", "four"]
    deck.addFact(f)
    assert len(deck.tags.selTagFids(["one"], [])) == 2
    assert len(deck.tags.selTagFids(["three"], [])) == 3
    assert len(deck.tags.selTagFids([], ["three"])) == 0
    assert len(deck.tags.selTagFids(["one"], ["three"])) == 0
    assert len(deck.tags.selTagFids(["one"], ["two"])) == 1
    assert len(deck.tags.selTagFids(["two", "three"], [])) == 3
    assert len(deck.tags.selTagFids(["two", "three"], ["one"])) == 1
    assert len(deck.tags.selTagFids(["one", "three"], ["two", "four"])) == 1
    deck.tags.setGroupForTags(["three"], [], 3)
    assert deck.db.scalar("select count() from cards where gid = 3") == 3
    deck.tags.setGroupForTags(["one"], [], 2)
    assert deck.db.scalar("select count() from cards where gid = 2") == 2

def test_addDelTags():
    deck = getEmptyDeck()
    f = deck.newFact()
    f['Front'] = u"1"
    deck.addFact(f)
    f2 = deck.newFact()
    f2['Front'] = u"2"
    deck.addFact(f2)
    # adding for a given id
    deck.tags.bulkAdd([f.id], "foo")
    f.load(); f2.load()
    assert "foo" in f.tags
    assert "foo" not in f2.tags
    # should be canonified
    deck.tags.bulkAdd([f.id], "foo aaa")
    f.load()
    assert f.tags[0] == "aaa"
    assert len(f.tags) == 2

def test_timestamps():
    deck = getEmptyDeck()
    assert len(deck.models.models) == 2
    for i in range(100):
        addBasicModel(deck)
    assert len(deck.models.models) == 102

