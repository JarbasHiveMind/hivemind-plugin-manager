import abc
import json
from dataclasses import dataclass, field
from typing import List, Dict, Union, Any, Optional, Iterable


ClientDict = Dict[str, Union[str, int, float, List[str]]]
ClientTypes = Union[None, 'Client',
                    str,  # json
                    ClientDict,  # dict
                    List[Union[str, ClientDict, 'Client']]  # list of dicts/json/Client
                ]


def cast2client(ret: ClientTypes) -> Optional[Union['Client', List['Client']]]:
    """
    Convert different input types (str, dict, list) to Client instances.

    Args:
        ret: The object to be cast, can be a string, dictionary, or list.

    Returns:
        A single Client instance or a list of Clients if ret is a list.
    """
    if ret is None or isinstance(ret, Client):
        return ret
    if isinstance(ret, str) or isinstance(ret, dict):
        return Client.deserialize(ret)
    if isinstance(ret, list):
        return [cast2client(r) for r in ret]
    raise TypeError("not a client object")


@dataclass
class Client:
    client_id: int
    api_key: str
    name: str = ""
    description: str = ""
    is_admin: bool = False
    last_seen: float = -1
    intent_blacklist: List[str] = field(default_factory=list)
    skill_blacklist: List[str] = field(default_factory=list)
    message_blacklist: List[str] = field(default_factory=list)
    allowed_types: List[str] = field(default_factory=list)
    crypto_key: Optional[str] = None
    password: Optional[str] = None
    can_broadcast: bool = True
    can_escalate: bool = True
    can_propagate: bool = True

    def __post_init__(self):
        """
        Initializes the allowed types for the Client instance if not provided.
        """
        if not isinstance(self.client_id, int):
            raise ValueError("client_id should be an integer")
        if not isinstance(self.is_admin, bool):
            raise ValueError("is_admin should be a boolean")
        self.allowed_types = self.allowed_types or ["recognizer_loop:utterance",
                                                    "recognizer_loop:record_begin",
                                                    "recognizer_loop:record_end",
                                                    "recognizer_loop:audio_output_start",
                                                    "recognizer_loop:audio_output_end",
                                                    'recognizer_loop:b64_transcribe',
                                                    'speak:b64_audio',
                                                    "ovos.common_play.SEI.get.response"]
        if "recognizer_loop:utterance" not in self.allowed_types:
            self.allowed_types.append("recognizer_loop:utterance")

    def serialize(self) -> str:
        """
        Serializes the Client instance into a JSON string.

        Returns:
            A JSON string representing the client data.
        """
        return json.dumps(self.__dict__, sort_keys=True, ensure_ascii=False)

    @staticmethod
    def deserialize(client_data: Union[str, Dict]) -> 'Client':
        """
        Deserialize a client from JSON string or dictionary into a Client instance.

        Args:
            client_data: The data to be deserialized, either a string or dictionary.

        Returns:
            A Client instance.
        """
        if isinstance(client_data, str):
            client_data = json.loads(client_data)
        # TODO filter kwargs with inspect
        return Client(**client_data)

    def __getitem__(self, item: str) -> Any:
        """
        Access attributes of the client via item access.

        Args:
            item: The name of the attribute.

        Returns:
            The value of the attribute.

        Raises:
            KeyError: If the attribute does not exist.
        """
        if hasattr(self, item):
            return getattr(self, item)
        raise KeyError(f"Unknown key: {item}")

    def __setitem__(self, key: str, value: Any):
        """
        Set attributes of the client via item access.

        Args:
            key: The name of the attribute.
            value: The value to set.

        Raises:
            ValueError: If the attribute does not exist.
        """
        if hasattr(self, key):
            setattr(self, key, value)
        else:
            raise ValueError(f"Unknown property: {key}")

    def __eq__(self, other: Any) -> bool:
        """
        Compares two Client instances for equality based on their serialized data.

        Args:
            other: The other Client or Client-compatible object to compare with.

        Returns:
            True if the clients are equal, False otherwise.
        """
        try:
            other = cast2client(other)
        except:
            pass
        if isinstance(other, Client):
            return self.serialize() == other.serialize()
        return False

    def __repr__(self) -> str:
        """
        Returns a string representation of the Client instance.

        Returns:
            A string representing the client.
        """
        return self.serialize()


class AbstractDB(abc.ABC):
    """
    Abstract base class for all database implementations.

    All database implementations should derive from this class and implement
    the abstract methods.
    """

    @abc.abstractmethod
    def add_item(self, client: Client) -> bool:
        """
        Add a client to the database.

        Args:
            client: The client to be added.

        Returns:
            True if the addition was successful, False otherwise.
        """
        pass

    def delete_item(self, client: Client) -> bool:
        """
        Delete a client from the database.

        Args:
            client: The client to be deleted.

        Returns:
            True if the deletion was successful, False otherwise.
        """
        # leave the deleted entry in db, do not allow reuse of client_id !
        client = Client(client_id=client.client_id, api_key="revoked")
        return self.update_item(client)

    def update_item(self, client: Client) -> bool:
        """
        Update an existing client in the database.

        Args:
            client: The client to be updated.

        Returns:
            True if the update was successful, False otherwise.
        """
        return self.add_item(client)

    def replace_item(self, old_client: Client, new_client: Client) -> bool:
        """
        Replace an old client with a new client.

        Args:
            old_client: The old client to be replaced.
            new_client: The new client to add.

        Returns:
            True if the replacement was successful, False otherwise.
        """
        self.delete_item(old_client)
        return self.add_item(new_client)

    @abc.abstractmethod
    def search_by_value(self, key: str, val: Union[str, bool, int, float]) -> List[Client]:
        """
        Search for clients by a specific key-value pair.

        Args:
            key: The key to search by.
            val: The value to search for.

        Returns:
            A list of clients that match the search criteria.
        """
        pass

    @abc.abstractmethod
    def __len__(self) -> int:
        """
        Get the number of items in the database.

        Returns:
            The number of items in the database.
        """
        return 0

    @abc.abstractmethod
    def __iter__(self) -> Iterable['Client']:
        """
        Iterate over all clients in the database.

        Returns:
            An iterator over the clients in the database.
        """
        pass

    def sync(self):
        """update db from disk if needed"""
        pass

    def commit(self) -> bool:
        """
        Commit changes to the database.

        Returns:
            True if the commit was successful, False otherwise.
        """
        return True

